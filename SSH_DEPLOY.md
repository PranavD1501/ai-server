# SSH chatbot gateway

The gateway opens the Q&A interface directly over SSH and calls the existing Render backend. Customers need only an SSH client. No Python, downloaded script, or pip installation is needed on their computer.

```text
ssh -p 2222 chat@YOUR_SERVER
Password:
Connected to AI chat. Type exit to quit, /clear to reset.
You: Write a C program to reverse a string
AI: ...
You: Explain the loop
AI: ...
You: exit
Goodbye!
```

The host must accept public TCP connections. Render web services cannot provide this public SSH listener. No VPS has been provisioned yet.

## Run locally

Use Python 3.10 or later on the gateway host:

```sh
python -m pip install -r requirements-ssh.txt
cp .env.ssh.example .env.ssh
```

On Windows use `Copy-Item .env.ssh.example .env.ssh`. Edit `.env.ssh` to set a long private `SSH_CHAT_PASSWORD`. The gateway refuses to start without one. The optional backend token stays on the gateway. It does not need the Gemini key.

```sh
python ssh_gateway.py
ssh -p 2222 chat@localhost
```

The default listener is local-only. Code blocks are highlighted when the SSH client requests a terminal; plain sessions preserve original Markdown and indentation. Type `exit`, `/exit`, or press Ctrl+D/Ctrl+C to close. Idle sessions close after 30 minutes. Each session keeps the latest 10 exchanges in memory and clears them on disconnect. The gateway does not save chat transcripts.

## Deploy on a Linux VPS with Docker Compose

Copy the repository to your server, create `.env.ssh` as above, then:

```sh
docker compose --env-file .env.ssh -f compose.ssh.yml up -d --build
docker compose --env-file .env.ssh -f compose.ssh.yml logs --tail=20
```

Allow inbound TCP 2222 in the provider firewall and host firewall. Keep administrator SSH separate. The named volume persists the gateway's SSH host key across restarts; preserve and back it up so clients see a stable fingerprint. Verify the fingerprint printed at startup before accepting the first connection.

For the shorter command `ssh chat@chat.your-domain.com`, point a DNS A/AAAA record to the VPS and configure `SSH_PUBLIC_PORT=22` in `.env.ssh` only when port 22 is available for this gateway. Many VPSs already use 22 for administrator SSH: do not replace or disable that access blindly. Until a separate administration path is configured and verified, use the explicit `-p 2222` command.

The container runs as a non-root user with a read-only application filesystem. It offers no OS shell, remote commands, SFTP, SCP, or port forwarding. Questions are sent to Render and Gemini. SSH clients, shell history, known_hosts, provider/network logs, and the backend can still leave records; this is not a guarantee of traceless use.

This first version uses one shared chat login. Before selling subscriptions, add per-customer credentials, revocation, and usage limits. Do not share administrator credentials with customers.

## Test

Install the main and SSH requirements, then run:

```sh
python -m unittest discover -s tests -v
```
