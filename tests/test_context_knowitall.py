import copy
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import sys
import tempfile
import time
import unittest
from engineer_context import bridge
from engineer_context.config import KnowitallBinding, Limits
from engineer_context.errors import InvalidCodeRequest
from engineer_context.knowitall import KnowitallClient, ProviderError, validate_response

EXAMPLES = Path(__file__).parent / 'fixtures/knowitall-v1'

def request():
    return json.loads((EXAMPLES / 'exact-dependency-request.json').read_text())

def response():
    return json.loads((EXAMPLES / 'dependency-response.json').read_text())

class KnowitallTests(unittest.TestCase):
    def test_owner_validator_rejects_wrong_project(self):
        result = response(); result['project_id'] = 'wrong'
        with self.assertRaises(ProviderError): validate_response(request(), result)

    def test_exact_snapshot_never_substitutes_current(self):
        result = response(); result['resolved']['snapshot_id'] = 'other'
        with self.assertRaises(ProviderError): validate_response(request(), result)

    def test_partial_ambiguity_and_pagination_are_preserved(self):
        result = json.loads((EXAMPLES / 'partial-response.json').read_text())
        req = request(); req['request_id'] = result['request_id']
        req['selector']['snapshot_id'] = 'snap-python-0002'
        req['selector']['generation_id'] = 'gen-python-0002'
        before = copy.deepcopy(result)
        validate_response(req, result)
        self.assertEqual(result, before)
        self.assertEqual(result['status'], 'partial')

    def test_missing_runtime_or_store_is_unavailable(self):
        with tempfile.TemporaryDirectory() as temp:
            binding = KnowitallBinding('p', 'r', Path(temp)/'absent', Path(temp)/'store')
            with self.assertRaises(ProviderError): KnowitallClient(binding, Limits()).describe()
            binding = KnowitallBinding('p', 'r', Path(sys.executable), Path(temp)/'absent')
            with self.assertRaises(ProviderError): KnowitallClient(binding, Limits()).query(request())

    def test_incomplete_store_is_refused_without_creating_state(self):
        with tempfile.TemporaryDirectory() as temp:
            store = Path(temp) / 'store'; store.mkdir()
            binding = KnowitallBinding('project-synthetic', 'repo-python-service', Path(sys.executable), store)
            with self.assertRaises(ProviderError):
                KnowitallClient(binding, Limits(timeout_seconds=5)).query(request())
            self.assertEqual(sorted(p.name for p in store.iterdir()), [])

    def test_large_request_to_a_runtime_that_never_reads_is_bounded(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ('stages', 'generations', 'current'): (root / name).mkdir()
            exe = root / 'runtime'
            exe.write_text(f'#!{sys.executable}\nimport time; time.sleep(60)\n'); exe.chmod(0o700)
            binding = KnowitallBinding('project-synthetic', 'repo-python-service', exe, root)
            query = request(); query['filler'] = 'x' * 400000
            started = time.monotonic()
            with self.assertRaises(ProviderError):
                KnowitallClient(binding, Limits(timeout_seconds=.2)).query(query)
            self.assertLess(time.monotonic() - started, 10)

    def test_provider_environment_without_the_consumer_can_still_describe(self):
        # Engineer and Knowitall may live in separate private environments, so
        # the bridge must run on an interpreter that cannot import this package.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ('stages', 'generations', 'current'): (root / name).mkdir()
            site = root / 'provider-site'
            metadata = site / 'knowitall_code_context-0.1.0.dist-info'; metadata.mkdir(parents=True)
            (metadata / 'METADATA').write_text('Metadata-Version: 2.1\nName: knowitall-code-context\nVersion: 0.1.0\n')
            exe = root / 'provider-python'
            exe.write_text(f'''#!{sys.executable}
import runpy, sys
sys.path.insert(0, {str(site)!r})
class Blocked:
    def find_spec(self, name, path=None, target=None):
        if name.split('.')[0] == 'engineer_context': raise ModuleNotFoundError(name)
sys.meta_path.insert(0, Blocked())
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name='__main__')
''')
            exe.chmod(0o700)
            binding = KnowitallBinding('project-synthetic', 'repo-python-service', exe, root)
            info = KnowitallClient(binding, Limits(timeout_seconds=30)).describe()
            self.assertEqual(info['contract'], 'knowitall.code-context/v1')

    def test_bridge_reports_a_diagnosable_reason(self):
        with tempfile.TemporaryDirectory() as temp:
            output = io.StringIO()
            with redirect_stdout(output):
                status = bridge.main(['--store', temp, '--max-bytes', '1024'])
            self.assertEqual(status, 1)
            self.assertIn(json.loads(output.getvalue())['error'], bridge.REASONS)

    def test_rejected_request_reaches_the_caller_as_invalid_input(self):
        # The owning service answers a refused request with a valid response
        # carrying this status, so it must not read as a provider gap.
        self.assertTrue(bridge.rejected({'status':'invalid_request'}))
        self.assertFalse(bridge.rejected(response()))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ('stages', 'generations', 'current'): (root / name).mkdir()
            exe = root / 'runtime'
            exe.write_text(f'#!{sys.executable}\nprint(\'{{"error": "request-invalid"}}\')\nraise SystemExit(1)\n')
            exe.chmod(0o700)
            binding = KnowitallBinding('project-synthetic', 'repo-python-service', exe, root)
            with self.assertRaises(InvalidCodeRequest):
                KnowitallClient(binding, Limits(timeout_seconds=10)).query(request())

    def test_bridge_timeout_and_malformed_json_are_bounded(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ('stages', 'generations', 'current'): (root / name).mkdir()
            for body in ['import time; time.sleep(60)', 'print("bad json")', 'print("x" * 10000)']:
                exe = root / 'runtime'; exe.write_text(f'#!{sys.executable}\n{body}\n'); exe.chmod(0o700)
                binding = KnowitallBinding('project-synthetic', 'repo-python-service', exe, root)
                with self.assertRaises(ProviderError) as caught:
                    KnowitallClient(binding, Limits(timeout_seconds=.2, max_bytes=1024)).query(request())
                self.assertNotIn('bad json', str(caught.exception))
