import os
import requests
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

BRAVE_API_KEY = os.getenv("BRAVE_API_KEY")
JINA_BASE_URL = "https://r.jina.ai/"

SKIP_DOMAINS = [
    "youtube.com", "facebook.com", "twitter.com", "instagram.com",
    "tiktok.com", "zalo.me", "maps.google.com",
]

PREFERRED_DOMAINS = [
    "vnexpress.net", "kenh14.vn", "dantri.com.vn",
    "tripadvisor.com", "agoda.com", "booking.com",
    "traveloka.com", "foody.vn", "phunu.net.vn",
    "baomoi.com", "vietnamplus.vn",
]


def _search_brave_single(query: str, count: int = 10) -> list[str]:
    if not BRAVE_API_KEY:
        raise ValueError("BRAVE_API_KEY chưa được cấu hình trong .env")

    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": BRAVE_API_KEY,
    }
    params = {
        "q": query,
        "count": count,
        "country": "VN",
        "search_lang": "vi",
        "freshness": "py",  # past year
    }

    response = requests.get(
        "https://api.search.brave.com/res/v1/web/search",
        headers=headers,
        params=params,
        timeout=10,
    )
    response.raise_for_status()

    data = response.json()
    urls = []
    for item in data.get("web", {}).get("results", []):
        url = item.get("url", "")
        if url and not any(skip in url for skip in SKIP_DOMAINS):
            urls.append(url)

    return urls


def _sort_urls_by_quality(urls: list[str]) -> list[str]:
    def priority(url):
        for i, domain in enumerate(PREFERRED_DOMAINS):
            if domain in url:
                return i
        return len(PREFERRED_DOMAINS)

    return sorted(urls, key=priority)


def _extract_text_jina(url: str, max_chars: int = 4000, timeout: int = 15) -> str | None:
    try:
        jina_url = f"{JINA_BASE_URL}{url}"
        headers = {
            "Accept": "text/plain",
            "X-Return-Format": "text",
            "X-Timeout": str(timeout),
        }
        response = requests.get(jina_url, headers=headers, timeout=timeout + 2)

        if response.status_code == 200:
            text = response.text.strip()
            if len(text) < 150:
                return None
            return text[:max_chars]

        logger.warning(f"Jina returned {response.status_code} for {url}")
        return None

    except requests.exceptions.Timeout:
        logger.warning(f"Timeout extracting {url}")
        return None
    except Exception as e:
        logger.warning(f"Error extracting {url}: {e}")
        return None


def gather_reviews(destination: str, max_extract: int = 5, max_workers: int = 4) -> dict:
    queries = [
        f"{destination} review đánh giá kinh nghiệm du lịch",
        f"{destination} có nên đi không ưu nhược điểm",
    ]

    all_urls: list[str] = []
    for query in queries:
        try:
            urls = _search_brave_single(query, count=8)
            all_urls.extend(urls)
            logger.info(f"Query '{query}' → {len(urls)} URLs")
        except Exception as e:
            logger.error(f"Brave search failed for '{query}': {e}")

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_urls: list[str] = []
    for url in all_urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)

    unique_urls = _sort_urls_by_quality(unique_urls)

    review_data: dict = {
        "urls": unique_urls,
        "texts": [],
        "sources_found": len(unique_urls),
    }

    if not unique_urls:
        logger.warning("No URLs found after searching")
        return review_data

    # Extract a few extra in case some fail
    candidates = unique_urls[: max_extract + 4]
    extracted_texts: list[dict] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(_extract_text_jina, url): url for url in candidates
        }

        for future in as_completed(future_to_url, timeout=25):
            url = future_to_url[future]
            try:
                text = future.result()
                if text and len(text) > 200:
                    extracted_texts.append({"url": url, "text": text})
                    logger.info(f"Extracted {len(text)} chars from {url}")
                    if len(extracted_texts) >= max_extract:
                        break
            except Exception as e:
                logger.warning(f"Future failed for {url}: {e}")

    review_data["texts"] = extracted_texts
    return review_data
