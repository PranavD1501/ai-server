import unittest

import asyncssh
import httpx

import ssh_gateway


class GatewayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.requests = []

        async def backend(request):
            import json
            payload = json.loads(request.content)
            self.requests.append(payload)
            answer = '```python\ndef factorial(n):\n    return 120\n```' if len(self.requests) == 1 else 'It returns 120.'
            return httpx.Response(200, json={'response': answer})

        self.client = httpx.AsyncClient(transport=httpx.MockTransport(backend))
        self.key = asyncssh.generate_private_key('ssh-ed25519')
        self.listener = await ssh_gateway.start_gateway(
            '127.0.0.1', 0, self.key, 'chat', 'test-password', self.client, 'https://backend.test',
        )

    async def asyncTearDown(self):
        self.listener.close()
        await self.listener.wait_closed()
        await self.client.aclose()

    async def connect(self, password='test-password'):
        return await asyncssh.connect(
            '127.0.0.1', port=self.listener.get_port(), username='chat', password=password,
            client_keys=[], known_hosts=([self.key.convert_to_public()], [], []),
        )

    async def test_chat_context_code_clear_exit(self):
        async with await self.connect() as conn:
            async with conn.create_process(term_type='dumb') as process:
                await process.stdout.readuntil('You: ')
                process.stdin.write('Write factorial\n')
                answer = await process.stdout.readuntil('You: ')
                self.assertIn('    return 120', answer)
                process.stdin.write('What does it return for 5?\n')
                follow_up = await process.stdout.readuntil('You: ')
                self.assertIn('It returns 120.', follow_up)
                self.assertEqual(len(self.requests[1]['history']), 2)
                process.stdin.write('/clear\n')
                self.assertIn('Conversation cleared.', await process.stdout.readuntil('You: '))
                process.stdin.write('New question\n')
                await process.stdout.readuntil('You: ')
                self.assertEqual(self.requests[2]['history'], [])
                process.stdin.write('exit\n')
                result = await process.wait(timeout=5)
                self.assertEqual(result.exit_status, 0)
                self.assertIn('Goodbye!', result.stdout)

    async def test_invalid_password_rejected(self):
        with self.assertRaises(asyncssh.PermissionDenied):
            await self.connect(password='wrong')

    async def test_commands_and_forwarding_denied(self):
        async with await self.connect() as conn:
            result = await conn.run('uname -a', check=False)
            self.assertEqual(result.exit_status, 1)
            self.assertIn('interactive chat only', result.stderr)
            with self.assertRaises(asyncssh.ChannelOpenError):
                await conn.open_connection('127.0.0.1', 80)
            self.assertEqual(self.requests, [])

    async def test_eof_closes_cleanly(self):
        async with await self.connect() as conn:
            async with conn.create_process(term_type='dumb') as process:
                await process.stdout.readuntil('You: ')
                process.stdin.write_eof()
                result = await process.wait(timeout=5)
                self.assertEqual(result.exit_status, 0)

    async def test_password_required(self):
        with self.assertRaisesRegex(ValueError, 'required'):
            await ssh_gateway.start_gateway('127.0.0.1', 0, self.key, 'chat', '', self.client, 'https://backend.test')

    def test_output_strips_terminal_controls(self):
        self.assertEqual(ssh_gateway.clean_text('a\x1b[2J\x1b]0;title\x07b\n    c'), 'ab\n    c')


if __name__ == '__main__':
    unittest.main()
