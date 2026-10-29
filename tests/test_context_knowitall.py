import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from engineer_context.config import KnowitallBinding, Limits
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

    def test_bridge_timeout_and_malformed_json_are_bounded(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for body in ['import time; time.sleep(60)', 'print("bad json")', 'print("x" * 10000)']:
                exe = root / 'runtime'; exe.write_text(f'#!{sys.executable}\n{body}\n'); exe.chmod(0o700)
                binding = KnowitallBinding('project-synthetic', 'repo-python-service', exe, root)
                with self.assertRaises(ProviderError) as caught:
                    KnowitallClient(binding, Limits(timeout_seconds=.2, max_bytes=1024)).query(request())
                self.assertNotIn('bad json', str(caught.exception))
