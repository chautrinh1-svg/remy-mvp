# 🍴 Remy — AI Travel Review Assistant

Remy tổng hợp hàng trăm review du lịch từ nhiều nguồn và phân tích bằng AI, giúp bạn nắm bức tranh trung thực về một địa điểm trong vài giây.

---

## Architecture

```
User Question
     │
     ▼
Flask API (/api/analyze)
     │
     ├─► Groq (extract destination name)
     │
     ├─► Brave Search API ──► top URLs
     │
     ├─► Jina Reader (parallel) ──► full text per URL
     │
     └─► Groq LLM (structured analysis) ──► JSON response
```

**Free tier limits:**
| Service | Limit |
|---------|-------|
| Groq | 14,400 req/day |
| Brave Search | 2,000 queries/month |
| Jina Reader | Unlimited |

---

## Setup

### 1. Clone & install

```bash
cd remy-mvp/backend
pip install -r requirements.txt
```

### 2. API Keys

Copy `.env.example` → `.env` và điền API keys:

```bash
cp .env.example .env
```

**Lấy API keys miễn phí:**
- **Groq**: https://console.groq.com/keys → Create API Key
- **Brave Search**: https://brave.com/search/api/ → Free tier (2000 queries/month)

```
GROQ_API_KEY=gsk_xxxxxxxxxxxx
BRAVE_API_KEY=BSA_xxxxxxxxxxxx
```

### 3. Run backend

```bash
cd remy-mvp/backend
python app.py
```

Server chạy tại `http://localhost:5000`

### 4. Open frontend

Mở file `frontend/index.html` trực tiếp trong browser, hoặc dùng Live Server (VS Code extension).

---

## API Reference

### `POST /api/analyze`

**Request:**
```json
{ "question": "Có nên đi Vinpearl Nha Trang không?" }
```

**Response:**
```json
{
  "destination": "Vinpearl Nha Trang",
  "sources_analyzed": 14,
  "liked": [
    { "text": "Biển trong và đẹp", "count": 8, "quote": "nước xanh rõ đáy" }
  ],
  "complaints": [
    { "text": "Ban ngày rất nóng", "count": 11, "quote": "đỉnh nắng từ 10h-15h" }
  ],
  "truth_patterns": [
    {
      "pattern": "Ảnh đẹp vs thực tế",
      "insight": "Ảnh thường chụp lúc sáng sớm hoặc chiều mát, ban ngày thực tế rất nóng"
    }
  ],
  "traveler_fit": {
    "best_for": ["Nhóm bạn trẻ thích khám phá", "Budget traveler"],
    "avoid_if": ["Family có trẻ nhỏ dưới 5 tuổi", "Người thích resort tiện nghi"]
  },
  "neutral_summary": "Vinpearl Nha Trang...",
  "follow_up_questions": ["Tháng nào đi ít nóng nhất?", ...]
}
```

**Health check:**
```bash
curl http://localhost:5000/health
```

---

## Test Queries

```
1. Có nên đi Vinpearl Nha Trang không?
2. Review du lịch Phan Thiết Mũi Né
3. Cù Lao Câu có nên ngủ qua đêm không?
4. Review đồ ăn ở Hội An
5. Đà Lạt tháng mấy đẹp nhất?
```

---

## Performance

| Step | Time |
|------|------|
| Brave Search | ~1–2s |
| Jina Reader (5 URLs, parallel) | ~5–10s |
| Groq LLM | ~3–5s |
| **Total** | **~8–15s** |

Để cải thiện tốc độ: giảm `max_extract` xuống 3 trong `search_service.py`.

---

## File Structure

```
remy-mvp/
├── backend/
│   ├── app.py              # Flask API entry point
│   ├── search_service.py   # Brave Search + Jina Reader
│   ├── llm_service.py      # Groq destination extraction + analysis
│   ├── requirements.txt
│   └── .env                # Your API keys (git-ignored)
├── frontend/
│   ├── index.html          # UI
│   ├── style.css           # Dark theme styling
│   └── script.js           # Fetch + DOM rendering
└── README.md
```

---

## Troubleshooting

**"Không thể kết nối tới server"** → Backend chưa chạy. Chạy `python app.py` trong thư mục `backend/`.

**"BRAVE_API_KEY chưa được cấu hình"** → Kiểm tra file `.env` trong thư mục `backend/`.

**Kết quả chậm (>15s)** → Một số URL bị Jina timeout. Đây là bình thường, server vẫn trả kết quả từ các URL thành công.

**Groq trả JSON lỗi** → Hiếm khi xảy ra, thử lại query. Đã có fallback handling.
