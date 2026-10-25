"""Interactive terminal client. The Gemini API key stays on the server."""
import argparse
import os
import sys
from urllib.parse import urlsplit

import requests
from rich.console import Console
from rich.markdown import Markdown


def ask(session, url, prompt, history):
    try:
        response = session.post(
            url + "/chat", json={"prompt": prompt, "history": history}, timeout=(10, 120)
        )
        data = response.json()
    except requests.Timeout as exc:
        raise ValueError("The server took too long to respond. Please try again.") from exc
    except requests.RequestException as exc:
        raise ValueError("Cannot reach the server. Check the URL and your connection.") from exc
    except ValueError as exc:
        raise ValueError("The server returned an invalid response.") from exc
    if not isinstance(data, dict):
        raise ValueError("The server returned an invalid response.")
    if not response.ok:
        error = data.get("error")
        raise ValueError(error if isinstance(error, str) else "The server rejected the request.")
    answer = data.get("response")
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("The server returned no answer. Please try again.")
    return answer


def main(argv=None):
    parser = argparse.ArgumentParser(description="Connect once, then chat in your terminal.")
    parser.add_argument("url", nargs="?", default=os.getenv("AI_SERVER_URL", "http://127.0.0.1:5000"))
    parser.add_argument("--plain", action="store_true", help="Print original Markdown without styling")
    args = parser.parse_args(argv)
    url = args.url.rstrip("/")
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.query or parsed.fragment or parsed.username:
        parser.error("Use a server URL such as https://your-server.example.com")
    console = Console(highlight=False, markup=False)
    history = []
    with requests.Session() as session:
        token = os.getenv("AI_SERVER_TOKEN")
        if token:
            session.headers["Authorization"] = "Bearer " + token
        try:
            health = session.get(url + "/health", timeout=(10, 10))
            health.raise_for_status()
            if health.json().get("status") != "ok":
                raise ValueError("Server is not ready")
        except (requests.RequestException, ValueError, AttributeError):
            console.print("Cannot connect to a ready AI server. Check the URL and server configuration.", style="red")
            return 1
        console.print("Connected. Type /exit to quit, /clear to reset, or /help for commands.")
        while True:
            try:
                prompt = input("\nYou: ").strip()
            except (EOFError, KeyboardInterrupt):
                console.print("\nGoodbye!")
                break
            if not prompt:
                continue
            if prompt == "/exit":
                break
            if prompt == "/clear":
                history.clear()
                console.print("Conversation cleared.")
                continue
            if prompt == "/help":
                console.print("/exit: quit | /clear: reset conversation | /help: show commands")
                continue
            try:
                with console.status("Thinking..."):
                    answer = ask(session, url, prompt, history)
            except ValueError as exc:
                console.print(str(exc), style="red")
                continue
            except KeyboardInterrupt:
                console.print("\nRequest cancelled. Goodbye!")
                break
            console.print("\nAI:", style="bold cyan")
            if args.plain or not sys.stdout.isatty():
                print(answer)
            else:
                console.print(Markdown(answer, code_theme="monokai"))
            history.extend([{"role": "user", "text": prompt}, {"role": "model", "text": answer}])
            history = history[-20:]
    return 0


if __name__ == "__main__":
    sys.exit(main())
