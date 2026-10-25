# Terminal AI Q&A

Connect once, then type normal questions. Answers render as Markdown with syntax-highlighted code blocks, indentation, and line breaks. This is a Q&A client; it does not execute generated code.

## Run the server

Use Python 3.10 or newer. In this repository:

```sh
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in `GEMINI_API_KEY`. Keep this key on the server. `GEMINI_MODEL` can be any text model available to your key; the default is `gemini-flash-latest`.

```sh
python server.py
```

## Start chatting

On the lab computer, download `ai.py` and `requirements-client.txt`, then run:

```sh
python -m pip install -r requirements-client.txt
python ai.py https://your-deployed-server.example.com
```

For a server running on the same computer, use `python ai.py`.

```text
Connected. Type /exit to quit, /clear to reset, or /help for commands.

You: Write a Python function to reverse a string
AI:
    [The answer and syntax-highlighted code appear here.]

You: Explain how it works
```

Type `/clear` to reset the conversation, `/exit` to quit, or press Ctrl+C/Ctrl+D. The latest 10 exchanges are remembered in client memory, sent with each question, and discarded on exit. Nothing is saved to disk. Your questions and conversation context are sent to the hosted server and Gemini.

`python ai.py <url> --plain` prints original Markdown without colors or code-block borders for easy copying. Redirected output automatically uses this mode. Long lines may wrap to fit your terminal; use a wider terminal or plain output when copying code.

You can set `AI_SERVER_URL` once to omit the URL on later launches.

## Host for remote access

Deploy the repository to a Python hosting service with HTTPS. Set `GEMINI_API_KEY`, `GEMINI_MODEL`, and a long random `AI_SERVER_TOKEN` as server environment variables. Use this Linux production start command (the host normally supplies `PORT`):

```sh
gunicorn --bind 0.0.0.0:$PORT --timeout 120 server:app
```

Configure `/health` as the health-check path. It checks server configuration, not Gemini connectivity or API quota. The Flask development server is for local use.

Set the matching token in the lab terminal before connecting:

PowerShell:
```powershell
$env:AI_SERVER_TOKEN = "your-private-token"
$env:AI_SERVER_URL = "https://your-deployed-server.example.com"
python ai.py
```

Linux/macOS:
```sh
export AI_SERVER_TOKEN="your-private-token"
export AI_SERVER_URL="https://your-deployed-server.example.com"
python ai.py
```

Remote use requires the client file and Python dependencies; the URL itself does not launch an interactive shell. Use HTTPS for remote connections. Leaving the token empty allows anyone who can reach the server to use its Gemini quota. This small personal server has no per-user rate limiting; add hosting-level limits before sharing it widely.

## Tests

```sh
python -m unittest discover -s tests -v
```

Tests mock Gemini and HTTP calls; they do not spend API quota.
