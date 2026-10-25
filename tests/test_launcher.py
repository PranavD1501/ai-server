import os
import subprocess
import sys
import threading
import unittest
from unittest.mock import Mock, patch

from werkzeug.serving import make_server

import server


class LauncherTests(unittest.TestCase):
    def test_downloaded_client_without_packages(self):
        model = Mock()
        code = '```python\ndef factorial(n):\n    return 120\n```'
        model.models.generate_content.side_effect = [Mock(text=code), Mock(text='It returns 120.')]
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'test', 'AI_SERVER_TOKEN': ''}), \
                patch.object(server, 'client', model):
            http = make_server('127.0.0.1', 0, server.app)
            thread = threading.Thread(target=http.serve_forever, daemon=True)
            thread.start()
            try:
                url = 'http://127.0.0.1:%s' % http.server_port
                env = dict(os.environ, AI_SERVER_URL=url)
                # -I -S disables user site packages, PYTHONPATH, and site imports.
                launch = 'import urllib.request as u;exec(u.urlopen(%r).read())' % (url + '/cli')
                result = subprocess.run(
                    [sys.executable, '-I', '-S', '-c', launch],
                    input='Write factorial\nWhat does it return for 5?\n/clear\n/exit\n',
                    text=True, capture_output=True, env=env, timeout=20,
                )
            finally:
                http.shutdown()
                thread.join(timeout=5)
                http.server_close()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Connected.', result.stdout)
        self.assertIn(code, result.stdout)
        self.assertIn('It returns 120.', result.stdout)
        self.assertIn('Conversation cleared.', result.stdout)
        follow_up = model.models.generate_content.call_args_list[1].kwargs['contents']
        self.assertEqual([message.role for message in follow_up], ['user', 'model', 'user'])
        self.assertEqual(follow_up[1].parts[0].text, code)


if __name__ == '__main__':
    unittest.main()
