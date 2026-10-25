"""Download-and-run chat client using only Python's standard library."""
import json
import os
import socket
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def request_json(url, payload=None):
    headers = {"Content-Type": "application/json"}
    token = os.getenv("AI_SERVER_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    try:
        with urlopen(Request(url, data=body, headers=headers), timeout=120) as response:
            result = json.load(response)
    except HTTPError as exc:
        try:
            error = json.load(exc)
            message = error.get("error") if isinstance(error, dict) else None
        except (ValueError, OSError):
            message = None
        raise ValueError(message if isinstance(message, str) else "Server request failed (HTTP %s)." % exc.code) from exc
    except (URLError, socket.timeout, OSError) as exc:
        raise ValueError("Cannot reach the server, or it took too long. Please try again.") from exc
    except ValueError as exc:
        raise ValueError("The server returned an invalid response.") from exc
    if not isinstance(result, dict):
        raise ValueError("The server returned an invalid response.")
    return result


def main():
    url = os.getenv("AI_SERVER_URL", "https://ai-server-f5l7.onrender.com").rstrip("/")
    history = []
    try:
        if request_json(url + "/health").get("status") != "ok":
            raise ValueError("Server is not ready.")
    except ValueError as exc:
        print(str(exc))
        return 1
    print("Connected. Type /exit to quit, /clear to reset, or /help for commands.")
    while True:
        try:
            prompt = input("\nYou: ").strip()
            if prompt == "/exit":
                break
            if not prompt:
                continue
            if prompt == "/clear":
                history.clear()
                print("Conversation cleared.")
                continue
            if prompt == "/help":
                print("/exit: quit | /clear: reset | /help: commands")
                continue
            print("Thinking...", flush=True)
            result = request_json(url + "/chat", {"prompt": prompt, "history": history})
            answer = result.get("response")
            if not isinstance(answer, str) or not answer.strip():
                raise ValueError("The server returned no answer. Try again.")
            # Raw Markdown preserves code indentation and line breaks for copying.
            print("\nAI:\n" + answer)
            history.extend([{"role": "user", "text": prompt}, {"role": "model", "text": answer}])
            history = history[-20:]
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break
        except ValueError as exc:
            print(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
