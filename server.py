from flask import Flask, request, jsonify
from google import genai
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)

# Initializing the Gemini Client
# Ensure your .env file now has GEMINI_API_KEY
client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

@app.route("/")
def home():
    return "Gemini Terminal Server Running"

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()

    if not data or "prompt" not in data:
        return jsonify({
            "error": "Prompt required"
        }), 400

    prompt = data["prompt"]

    try:
        # Using gemini-3.1-flash (the standard high-speed model for 2026)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        # Gemini returns text directly via the .text attribute
        answer = response.text

        return jsonify({
            "response": answer
        })

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500

if __name__ == "__main__":
    app.run(debug=True)