"""Small Gemini Q&A API for the terminal client."""
import hmac
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_file
from google import genai
from google.genai import types

load_dotenv()
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 128 * 1024
client = None


@app.get("/")
def home():
    return (
        "AI terminal server running. Start a chat with Python 3:\n"
        'python -c "import urllib.request as u;exec(u.urlopen(\'https://ai-server-f5l7.onrender.com/cli\',timeout=90).read())"\n'
    )


@app.get("/cli")
def terminal_client():
    return send_file(Path(__file__).with_name("terminal.py"), mimetype="text/x-python", max_age=0)


@app.get("/health")
def health():
    ready = bool(os.getenv("GEMINI_API_KEY"))
    return jsonify(status="ok" if ready else "not_configured"), 200 if ready else 503


@app.errorhandler(413)
def too_large(_error):
    return jsonify(error="Conversation too large. Use /clear and try a shorter question."), 413


@app.post("/chat")
def chat():
    global client
    token = os.getenv("AI_SERVER_TOKEN")
    if token and not hmac.compare_digest(
        request.headers.get("Authorization", "").encode(), ("Bearer " + token).encode()
    ):
        return jsonify(error="Unauthorized. Set AI_SERVER_TOKEN on your client."), 401
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Send a JSON object with a prompt."), 400
    prompt = data.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 16000:
        return jsonify(error="Prompt must contain 1 to 16000 characters."), 400
    history = data.get("history", [])
    if not isinstance(history, list) or len(history) > 20 or len(history) % 2:
        return jsonify(error="History must contain at most 10 complete exchanges."), 400
    contents = []
    for index, message in enumerate(history):
        expected = "user" if index % 2 == 0 else "model"
        if (not isinstance(message, dict) or message.get("role") != expected
                or not isinstance(message.get("text"), str) or not message["text"].strip()):
            return jsonify(error="History must alternate user and model text messages."), 400
        contents.append(types.Content(role=expected, parts=[types.Part.from_text(text=message["text"])]))
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=prompt)]))
    if not os.getenv("GEMINI_API_KEY"):
        return jsonify(error="Server is missing GEMINI_API_KEY."), 503
    try:
        if client is None:
            client = genai.Client(api_key=os.environ["GEMINI_API_KEY"], http_options=types.HttpOptions(timeout=90000))
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-flash-latest"),
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=(
                "You are a helpful Q&A and coding assistant. Answer clearly and concisely. "
                "Put all code in fenced Markdown code blocks with a language tag. "
                "Preserve code indentation and line breaks. Explain when you are uncertain."
            )),
        )
        if not response.text or not response.text.strip():
            return jsonify(error="The AI returned no text. Try rephrasing your question."), 502
        return jsonify(response=response.text)
    except Exception:
        app.logger.exception("AI generation failed")
        return jsonify(error="AI service unavailable. Please try again shortly."), 502


if __name__ == "__main__":
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "5000")))
