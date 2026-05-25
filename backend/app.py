from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import os
import logging

load_dotenv()

from search_service import gather_reviews
from llm_service import analyze_reviews, extract_destination

app = Flask(__name__)
CORS(app)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "Remy AI Travel Review"})


@app.route("/api/analyze", methods=["POST"])
def analyze():
    try:
        data = request.get_json(force=True, silent=True)
        if not data:
            return jsonify({"error": "Vui lòng gửi JSON body"}), 400

        question = data.get("question", "").strip()
        if not question:
            return jsonify({"error": "Vui lòng nhập câu hỏi"}), 400
        if len(question) < 5:
            return jsonify({"error": "Câu hỏi quá ngắn, vui lòng nhập rõ hơn"}), 400

        logger.info(f"Received question: {question}")

        destination = extract_destination(question)
        logger.info(f"Destination extracted: {destination}")

        review_data = gather_reviews(destination)
        logger.info(
            f"Gathered {len(review_data['texts'])} texts from "
            f"{review_data['sources_found']} URLs found"
        )

        result = analyze_reviews(destination, review_data)
        return jsonify(result)

    except ValueError as e:
        logger.error(f"Config error: {e}")
        return jsonify({"error": f"Lỗi cấu hình: {str(e)}"}), 500
    except Exception as e:
        logger.exception("Unexpected error during analyze")
        return jsonify({"error": f"Có lỗi xảy ra: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000, host="0.0.0.0")
