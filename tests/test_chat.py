import io
import os
import unittest
from unittest.mock import Mock, patch

import requests
from rich.console import Console
from rich.markdown import Markdown

import ai
import server


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"GEMINI_API_KEY": "test-key", "AI_SERVER_TOKEN": ""})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.model = Mock()
        self.model.models.generate_content.return_value.text = "```python\ndef hello():\n    return 'hi'\n```"
        self.client_patch = patch.object(server, "client", self.model)
        self.client_patch.start()
        self.addCleanup(self.client_patch.stop)
        self.http = server.app.test_client()

    def test_follow_up_preserves_roles_and_code(self):
        response = self.http.post("/chat", json={"prompt": "Explain it", "history": [
            {"role": "user", "text": "Write hello"},
            {"role": "model", "text": "def hello():\n    return 'hi'"},
        ]})
        self.assertEqual(response.status_code, 200)
        self.assertIn("\n    return 'hi'", response.json["response"])
        contents = self.model.models.generate_content.call_args.kwargs["contents"]
        self.assertEqual([m.role for m in contents], ["user", "model", "user"])
        self.assertEqual(contents[1].parts[0].text, "def hello():\n    return 'hi'")

    def test_invalid_inputs_never_call_model(self):
        for data in ([], {}, {"prompt": 42}, {"prompt": " "},
                     {"prompt": "Hi", "history": [{}]},
                     {"prompt": "Hi", "history": [{"role": "model", "text": "x"}] * 2}):
            with self.subTest(data=data):
                self.assertEqual(self.http.post("/chat", json=data).status_code, 400)
        self.model.models.generate_content.assert_not_called()

    def test_authentication(self):
        with patch.dict(os.environ, {"AI_SERVER_TOKEN": "private"}):
            self.assertEqual(self.http.post("/chat", json={"prompt": "Hi"}).status_code, 401)
            self.assertEqual(self.http.post("/chat", json={"prompt": "Hi"},
                             headers={"Authorization": "Bearer private"}).status_code, 200)

    def test_upstream_failure_is_safe(self):
        self.model.models.generate_content.side_effect = RuntimeError("secret provider error")
        with patch.object(server.app.logger, "exception"):
            response = self.http.post("/chat", json={"prompt": "Hi"})
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("secret", response.get_data(as_text=True))

    def test_missing_key_and_oversized_request(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            self.assertEqual(self.http.get("/health").status_code, 503)
            self.assertEqual(self.http.post("/chat", json={"prompt": "Hi"}).status_code, 503)
        self.assertEqual(self.http.post("/chat", json={"prompt": "x" * 150000}).status_code, 413)


class ClientTests(unittest.TestCase):
    def test_errors_are_readable(self):
        session = Mock()
        session.post.side_effect = requests.Timeout()
        with self.assertRaisesRegex(ValueError, "too long"):
            ai.ask(session, "https://example.com", "Hi", [])
        session.post.side_effect = None
        session.post.return_value.json.return_value = {"error": "Unauthorized"}
        session.post.return_value.ok = False
        with self.assertRaisesRegex(ValueError, "Unauthorized"):
            ai.ask(session, "https://example.com", "Hi", [])

    def test_chat_clear_and_plain_code(self):
        session = Mock()
        session.get.return_value.json.return_value = {"status": "ok"}
        code = "```python\ndef hello():\n    return 'hi'\n```"
        seen = []

        def reply(_session, _url, prompt, history):
            seen.append((prompt, list(history)))
            return code

        out = io.StringIO()
        with patch("ai.requests.Session") as factory, patch("ai.ask", side_effect=reply), \
                patch("builtins.input", side_effect=["First", "Explain", "/clear", "Again", "/exit"]), \
                patch("sys.stdout", out):
            factory.return_value.__enter__.return_value = session
            self.assertEqual(ai.main(["https://example.com", "--plain"]), 0)
        self.assertEqual(len(seen[1][1]), 2)
        self.assertEqual(seen[2][1], [])
        self.assertIn(code, out.getvalue())

    def test_markdown_renders_indented_code(self):
        out = io.StringIO()
        console = Console(file=out, width=80, force_terminal=True, color_system=None)
        console.print(Markdown("```python\ndef hello():\n    return 'hi'\n```"))
        rendered = out.getvalue()
        self.assertIn("def hello():", rendered)
        self.assertIn("    return 'hi'", rendered)


if __name__ == "__main__":
    unittest.main()
