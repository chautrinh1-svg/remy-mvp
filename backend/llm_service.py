import os
import json
import logging
from groq import Groq

logger = logging.getLogger(__name__)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """\
Bạn là Remy, AI phân tích review du lịch trung lập và chuyên nghiệp tại Việt Nam.

NHIỆM VỤ: Phân tích đánh giá du lịch từ nhiều nguồn, trả về JSON theo đúng schema.

RULES TUYỆT ĐỐI:
1. Chỉ trích dẫn từ review thật được cung cấp - KHÔNG bịa đặt bất kỳ quote nào
2. "count" là ước tính số lần topic được nhắc đến trong tổng số nguồn
3. Trung lập - không dùng từ "nên đi" hay "không nên đi"
4. Phát hiện truth patterns: ảnh vs thực tế, contradictions, hidden timing tips
5. Traveler-fit phải cụ thể và thực tế, dựa trên nội dung review
6. neutral_summary 2-3 câu, phải chứa ít nhất một quote ngắn từ review gốc
7. Output: JSON object thuần túy - KHÔNG markdown, KHÔNG ```json wrapper, KHÔNG giải thích

JSON SCHEMA BẮT BUỘC:
{
  "destination": "tên đầy đủ địa điểm",
  "sources_analyzed": <number>,
  "liked": [
    {"text": "điểm cụ thể được thích", "count": <number>, "quote": "trích dẫn thật từ review"}
  ],
  "complaints": [
    {"text": "phàn nàn cụ thể", "count": <number>, "quote": "trích dẫn thật từ review"}
  ],
  "truth_patterns": [
    {"pattern": "tên pattern ngắn", "insight": "giải thích chi tiết dựa trên review"}
  ],
  "traveler_fit": {
    "best_for": ["nhóm phù hợp cụ thể"],
    "avoid_if": ["nhóm không phù hợp cụ thể"]
  },
  "neutral_summary": "2-3 câu tóm tắt trung lập có quote",
  "follow_up_questions": ["câu hỏi 1?", "câu hỏi 2?", "câu hỏi 3?"]
}\
"""


def extract_destination(question: str) -> str:
    """Extract the destination name from a user question."""
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Trích xuất tên địa điểm du lịch từ câu hỏi tiếng Việt. "
                        "Chỉ trả về tên địa điểm đầy đủ, không giải thích, không dấu chấm. "
                        "Ví dụ: 'Vinpearl Nha Trang', 'Cù Lao Câu', 'Phú Quốc', 'Đà Lạt'."
                    ),
                },
                {"role": "user", "content": question},
            ],
            max_tokens=60,
            temperature=0,
        )
        return response.choices[0].message.content.strip().rstrip(".")
    except Exception as e:
        logger.error(f"extract_destination failed: {e}")
        return question  # Fallback: use full question as destination


def analyze_reviews(destination: str, review_data: dict) -> dict:
    """Send gathered reviews to Groq and return structured analysis."""
    texts: list[dict] = review_data.get("texts", [])
    sources_found: int = review_data.get("sources_found", 0)

    # Build combined review text
    combined_parts = []
    for i, item in enumerate(texts, 1):
        domain = item["url"].split("/")[2] if "/" in item["url"] else item["url"]
        combined_parts.append(
            f"=== NGUỒN {i} [{domain}] ===\n{item['text']}"
        )

    combined = "\n\n".join(combined_parts)
    if not combined.strip():
        combined = (
            f"Không tìm thấy đủ nội dung review cho '{destination}'. "
            "Hãy trả về JSON với các trường rỗng và neutral_summary giải thích."
        )

    # Truncate to fit context (leave room for system prompt + response)
    combined = combined[:14000]

    user_message = (
        f'Phân tích các đánh giá về "{destination}".\n\n'
        f"Tổng URLs tìm được: {sources_found} | Đã đọc nội dung: {len(texts)} nguồn\n\n"
        f"NỘI DUNG REVIEW:\n{combined}\n\n"
        f"YÊU CẦU OUTPUT:\n"
        f'- "sources_analyzed" = {sources_found}\n'
        f"- liked: 3-5 điểm nổi bật được nhắc nhiều nhất\n"
        f"- complaints: 2-4 vấn đề phổ biến\n"
        f"- truth_patterns: 2-3 patterns thú vị (ảnh vs thực tế, timing, hidden tips)\n"
        f"- follow_up_questions: 3 câu hỏi người đọc sẽ muốn tìm hiểu tiếp\n"
        f"Trả về JSON object hợp lệ theo schema đã định nghĩa."
    )

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            max_tokens=2500,
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content.strip()
        result = json.loads(content)

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e} | content: {content[:300]}")
        result = _fallback_response(destination, sources_found)
    except Exception as e:
        logger.exception(f"Groq API error for '{destination}'")
        raise

    _fill_missing_fields(result, destination, sources_found)
    return result


def _fill_missing_fields(result: dict, destination: str, sources_found: int) -> None:
    result.setdefault("destination", destination)
    result.setdefault("sources_analyzed", sources_found)
    result.setdefault("liked", [])
    result.setdefault("complaints", [])
    result.setdefault("truth_patterns", [])
    tf = result.setdefault("traveler_fit", {})
    tf.setdefault("best_for", [])
    tf.setdefault("avoid_if", [])
    result.setdefault(
        "neutral_summary",
        f"Chưa tìm đủ dữ liệu để phân tích {destination}.",
    )
    result.setdefault("follow_up_questions", [])


def _fallback_response(destination: str, sources_found: int) -> dict:
    return {
        "destination": destination,
        "sources_analyzed": sources_found,
        "liked": [],
        "complaints": [],
        "truth_patterns": [],
        "traveler_fit": {"best_for": [], "avoid_if": []},
        "neutral_summary": f"Không thể phân tích dữ liệu về {destination} lúc này. Vui lòng thử lại.",
        "follow_up_questions": [],
    }
