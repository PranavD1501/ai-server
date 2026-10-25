"""SSH-only chatbot gateway. No operating-system shell is exposed."""
import asyncio
import hmac
import io
import os
from pathlib import Path
import re

import asyncssh
import httpx
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown


def clean_text(text):
    # Model output must not inject terminal escape/control sequences.
    text = re.sub(r'\x1b\][^\x07]*(?:\x07|\x1b\\)', '', text)
    text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', text)
    return ''.join(c for c in text if c in '\n\t' or (ord(c) >= 32 and ord(c) != 127))


class ChatServer(asyncssh.SSHServer):
    def __init__(self, username, password):
        self.username, self.password = username, password

    def begin_auth(self, username):
        return True

    def password_auth_supported(self):
        return True

    def validate_password(self, username, password):
        return (hmac.compare_digest(username.encode(), self.username.encode())
                and hmac.compare_digest(password.encode(), self.password.encode()))


async def chat_session(process, client, backend):
    if process.command or process.subsystem:
        process.stderr.write('This service accepts interactive chat only.\n')
        process.exit(1)
        return
    history = []
    process.stdout.write('Connected to AI chat. Type exit to quit, /clear to reset.\n')
    try:
        while True:
            process.stdout.write('\nYou: ')
            line = await asyncio.wait_for(process.stdin.readline(), timeout=1800)
            if not line:
                break
            prompt = line.strip()
            if prompt.lower() in ('exit', '/exit', 'quit', '/quit'):
                break
            if not prompt:
                continue
            if prompt == '/clear':
                history.clear()
                process.stdout.write('Conversation cleared.\n')
                continue
            if prompt == '/help':
                process.stdout.write('exit: quit | /clear: reset | /help: commands\n')
                continue
            if len(prompt) > 16000:
                process.stdout.write('Please keep questions under 16000 characters.\n')
                continue
            process.stdout.write('Thinking...\n')
            try:
                response = await client.post(backend + '/chat', json={'prompt': prompt, 'history': history})
                data = response.json()
                if not response.is_success:
                    error = data.get('error') if isinstance(data, dict) else None
                    raise ValueError(error if isinstance(error, str) else 'Server request failed.')
                answer = data.get('response') if isinstance(data, dict) else None
                if not isinstance(answer, str) or not answer.strip():
                    raise ValueError('The AI returned no answer. Try again.')
            except httpx.HTTPError:
                process.stdout.write('The AI server is unreachable or slow. Please try again.\n')
                continue
            except ValueError as exc:
                message = str(exc) if response.is_success is False else 'The AI returned an invalid response.'
                process.stdout.write(clean_text(message) + '\n')
                continue
            process.stdout.write('\nAI:\n')
            safe_answer = clean_text(answer)
            if process.term_type and process.term_type != 'dumb':
                output = io.StringIO()
                width = min(240, max(40, process.term_size[0] or 80))
                console = Console(file=output, force_terminal=True, width=width, color_system='standard')
                console.print(Markdown(safe_answer, code_theme='monokai'))
                process.stdout.write(output.getvalue())
            else:
                process.stdout.write(safe_answer + '\n')
            history.extend([{'role': 'user', 'text': prompt}, {'role': 'model', 'text': answer}])
            history = history[-20:]
    except (asyncssh.SignalReceived, asyncssh.BreakReceived, asyncio.TimeoutError):
        pass
    except (asyncssh.Error, ConnectionError):
        return
    finally:
        history.clear()
    process.stdout.write('Goodbye!\n')
    process.exit(0)


async def start_gateway(host, port, key, username, password, client, backend):
    if not password:
        raise ValueError('SSH_CHAT_PASSWORD is required.')
    return await asyncssh.create_server(
        lambda: ChatServer(username, password), host, port,
        server_host_keys=[key],
        process_factory=lambda process: chat_session(process, client, backend),
        line_editor=True, max_line_length=16001, login_timeout=30,
        allow_scp=False, sftp_factory=None,
    )


async def main():
    load_dotenv('.env.ssh')
    password = os.getenv('SSH_CHAT_PASSWORD', '')
    if not password:
        raise ValueError('Set SSH_CHAT_PASSWORD in .env.ssh before starting.')
    key_path = Path(os.getenv('SSH_HOST_KEY', 'ssh-data/ssh_host_ed25519_key'))
    key_path.parent.mkdir(parents=True, exist_ok=True)
    if not key_path.exists():
        key = asyncssh.generate_private_key('ssh-ed25519')
        # Exclusive creation, private permissions, and persistence across restarts.
        with os.fdopen(os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as out:
            out.write(key.export_private_key())
    headers = {}
    token = os.getenv('AI_SERVER_TOKEN')
    if token:
        headers['Authorization'] = 'Bearer ' + token
    backend = os.getenv('AI_SERVER_URL', 'https://ai-server-f5l7.onrender.com').rstrip('/')
    async with httpx.AsyncClient(headers=headers, timeout=120) as client:
        listener = await start_gateway(
            os.getenv('SSH_BIND_HOST', '127.0.0.1'), int(os.getenv('SSH_PORT', '2222')),
            str(key_path), os.getenv('SSH_CHAT_USER', 'chat'), password, client, backend,
        )
        print('SSH chat listening on port', listener.get_port(), flush=True)
        print('Host key fingerprint:', asyncssh.read_private_key(key_path).get_fingerprint(), flush=True)
        try:
            await listener.wait_closed()
        finally:
            listener.close()
            await listener.wait_closed()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
