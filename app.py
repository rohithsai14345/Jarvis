import os
import ast
import json
import operator
from pathlib import Path
from datetime import datetime

import requests
from flask import Flask, request, jsonify, send_from_directory

BASE_DIR = Path(__file__).resolve().parent
NOTES_FILE = BASE_DIR / "notes.json"

app = Flask(__name__)

API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{MODEL}:generateContent"
)


def load_notes():
    try:
        if NOTES_FILE.exists():
            with NOTES_FILE.open("r", encoding="utf-8") as file:
                data = json.load(file)
                return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        pass
    return []


def save_notes(notes):
    with NOTES_FILE.open("w", encoding="utf-8") as file:
        json.dump(notes, file, indent=2, ensure_ascii=False)


def calculate(expression):
    allowed_operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    def evaluate(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return node.value

        if isinstance(node, ast.BinOp) and type(node.op) in allowed_operators:
            left = evaluate(node.left)
            right = evaluate(node.right)

            if isinstance(node.op, ast.Pow) and abs(right) > 100:
                raise ValueError("Exponent is too large")

            result = allowed_operators[type(node.op)](left, right)

            if isinstance(result, (int, float)) and abs(result) > 1e100:
                raise ValueError("Result is too large")

            return result

        if isinstance(node, ast.UnaryOp) and type(node.op) in allowed_operators:
            return allowed_operators[type(node.op)](evaluate(node.operand))

        raise ValueError("Only basic arithmetic is allowed")

    if len(expression) > 100:
        raise ValueError("Expression is too long")

    tree = ast.parse(expression, mode="eval")
    return evaluate(tree.body)


def offline_reply(message):
    text = message.strip()
    lower = text.lower()

    if not text:
        return "Please type a message."

    if lower in ("hi", "hello", "hey"):
        return "Hello! I am JARVIS. How can I help you?"

    if lower in ("help", "commands"):
        return (
            "JARVIS commands:\n"
            "- time: show current time\n"
            "- date: show today's date\n"
            "- calculate 12 * 5: calculate a number\n"
            "- note Buy books: save a note\n"
            "- show notes: display saved notes\n"
            "- clear notes: delete all saved notes"
        )

    if lower == "time":
        return "Current time: " + datetime.now().strftime("%I:%M:%S %p")

    if lower == "date":
        return "Today's date: " + datetime.now().strftime("%d-%m-%Y")

    if lower == "status":
        return "JARVIS is running. Offline commands are available."

    if lower.startswith("calculate "):
        try:
            result = calculate(text[len("calculate "):])
            return f"Result: {result}"
        except Exception as error:
            return f"Could not calculate: {error}"

    if lower.startswith("note "):
        note_text = text[5:].strip()
        if not note_text:
            return "Please write something after 'note'."
        notes = load_notes()
        notes.append({
            "text": note_text,
            "created": datetime.now().isoformat(timespec="seconds"),
        })
        save_notes(notes)
        return "Note saved successfully."

    if lower == "show notes":
        notes = load_notes()
        if not notes:
            return "You have no saved notes."
        return "\n".join(
            f"{index}. {note.get('text', '')}"
            for index, note in enumerate(notes, start=1)
        )

    if lower == "clear notes":
        save_notes([])
        return "All notes have been cleared."

    if "what is python" in lower:
        return "Python is a programming language used for apps, automation, AI, and more."

    if "what is ai" in lower:
        return "AI means Artificial Intelligence. It enables computers to perform tasks that usually require human intelligence."

    return None


def ask_gemini(message, image=None):
    if not API_KEY:
        return None, "Gemini is not configured. Set GEMINI_API_KEY to enable AI responses."

    parts = [{"text": message}]

    if image:
        mime_type = image.get("mime_type", "")
        image_data = image.get("data", "")

        if mime_type not in ("image/jpeg", "image/png", "image/webp"):
            return None, "Please use a JPEG, PNG, or WEBP image."

        if not isinstance(image_data, str) or not image_data:
            return None, "The image data is missing."

        parts.append({
            "inline_data": {
                "mime_type": mime_type,
                "data": image_data,
            }
        })

    try:
        response = requests.post(
            GEMINI_URL,
            params={"key": API_KEY},
            json={"contents": [{"parts": parts}]},
            timeout=45,
        )
        response.raise_for_status()
        data = response.json()

        candidates = data.get("candidates", [])
        if not candidates:
            return None, "Gemini did not return an answer."

        answer_parts = candidates[0].get("content", {}).get("parts", [])
        answer = "\n".join(
            part["text"] for part in answer_parts if "text" in part
        )
        return answer or None, None

    except requests.RequestException as error:
        return None, f"Gemini request failed: {error}"
    except (ValueError, KeyError, TypeError):
        return None, "Gemini returned an unexpected response."


@app.route("/")
def home():
    index_file = BASE_DIR / "index.html"
    if index_file.exists():
        return send_from_directory(str(BASE_DIR), "index.html")
    return "JARVIS backend is running. Add your index.html to the JARVIS folder."


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "gemini_configured": bool(API_KEY),
    })


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    message = data.get("message", "")
    image = data.get("image")

    if not isinstance(message, str):
        return jsonify({"error": "Message must be text."}), 400

    if len(message) > 10000:
        return jsonify({"error": "Message is too long."}), 400

    if "news" in message.lower():
        text = message.lower()
        category = None

        if "technology" in text or "tech news" in text:
            category = "technology"
        elif "sports" in text:
            category = "sports"
        elif "business" in text:
            category = "business"
        elif "science" in text:
            category = "science"

        news_answer = get_news(category)

        return jsonify({
            "reply": news_answer,
            "mode": "news"
        })

    offline_answer = offline_reply(message)

    if offline_answer is not None:
        return jsonify({"reply": offline_answer, "mode": "offline"})

    answer, error = ask_gemini(message, image)

    if answer:
        return jsonify({"reply": answer, "mode": "gemini"})

    return jsonify({
        "reply": error or "Sorry, I could not generate a response.",
        "mode": "offline",
    })
def get_news(category=None):
    import requests
    import xml.etree.ElementTree as ET
    from urllib.parse import quote

    if category:
        query = f"{category} news India"
        url = (
            "https://news.google.com/rss/search?q="
            + quote(query)
            + "&hl=en-IN&gl=IN&ceid=IN:en"
        )
    else:
        url = "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en"

    try:
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        response.raise_for_status()

        root = ET.fromstring(response.content)
        articles = root.findall("./channel/item")

        if not articles:
            return "No news articles found. Please try again later."

        results = ["Latest India News:"]

        for i, article in enumerate(articles[:5], start=1):
            title = article.findtext("title", "Untitled")
            link = article.findtext("link", "")
            source = article.findtext("source", "Google News")

            results.append(
                f"{i}. {title}\n"
                f"Source: {source}\n"
                f"Link: {link}"
            )

        return "\n\n".join(results)

    except requests.RequestException:
        return "Unable to connect to Google News. Check your internet."
    except ET.ParseError:
        return "Unable to read the news feed. Please try again later."

@app.errorhandler(413)
def request_too_large(error):
    return jsonify({"error": "Request is too large."}), 413


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)

