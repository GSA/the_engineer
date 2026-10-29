import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from engineer_context.config import LibrarianBinding, Limits
from engineer_context.librarian import LibrarianClient, ProviderError

class LibrarianTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        # Trusted executable shim runs the component-owned failure server.
        self.exe = self.root / 'librarian-mcp'
        fixture = Path(__file__).with_name('context_mcp_fixture.py')
        self.exe.write_text(f'#!{sys.executable}\nimport runpy\nrunpy.run_path({str(fixture)!r}, run_name="__main__")\n')
        self.exe.chmod(0o700)
        self.binding = LibrarianBinding('business-1', self.exe, fixture, self.root)

    async def test_single_text_json_preserves_qualification(self):
        async with LibrarianClient.open(self.binding, Limits()) as client:
            self.assertEqual((await client.describe())['identity_kind'], 'configured')
            self.assertTrue((await client.status())['fresh'])
            result = await client.get('doc.md#section')
            self.assertEqual(result['handling'], ['private'])
            self.assertEqual(result['pieces'][0]['text'], 'Exact passage')

    async def test_wrong_server_or_missing_tool_is_unavailable(self):
        for mode in ['wrong', 'missing']:
            with patch.dict(os.environ, CONTEXT_TEST_MODE=mode), self.assertRaises(ProviderError):
                async with LibrarianClient.open(self.binding, Limits()): pass

    async def test_stale_or_error_result_is_refused(self):
        for mode in ['stale', 'error']:
            with patch.dict(os.environ, CONTEXT_TEST_MODE=mode):
                async with LibrarianClient.open(self.binding, Limits()) as client:
                    with self.assertRaises(ProviderError):
                        if mode == 'stale': await client.status()
                        else: await client.get('doc.md#section')

    async def test_timeout_cleans_up_process(self):
        pid_path = self.root / 'pid'
        with patch.dict(os.environ, CONTEXT_TEST_MODE='hang', CONTEXT_TEST_PID=str(pid_path)):
            with self.assertRaises(ProviderError):
                async with LibrarianClient.open(self.binding, Limits(timeout_seconds=2)) as client:
                    await client.status()
        pid = int(pid_path.read_text())
        with self.assertRaises(ProcessLookupError): os.kill(pid, 0)

    async def test_oversized_result_is_refused(self):
        with patch.dict(os.environ, CONTEXT_TEST_MODE='large'):
            async with LibrarianClient.open(self.binding, Limits(max_bytes=4096)) as client:
                with self.assertRaises(ProviderError): await client.get('doc.md#section')
