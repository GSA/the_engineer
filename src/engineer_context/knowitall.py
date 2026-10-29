"""Read-only bridge into an explicitly installed owning query implementation."""
import argparse
from dataclasses import asdict
from importlib.metadata import version
import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
import time
from .librarian import ProviderError
from .packet import canonical_bytes


def validate_response(request, response):
    try:
        from knowitall_contract.validation import validate_query_request, validate_query_response
        validate_query_request(request)
        validate_query_response(response, expected_request=request)
        if request['selector']['mode'] == 'exact' and response.get('resolved') is not None:
            for field in ['snapshot_id', 'generation_id']:
                if response['resolved'][field] != request['selector'][field]:
                    raise ValueError()
    except Exception:
        raise ProviderError('invalid', 'Knowitall contract or identity validation failed') from None


class KnowitallClient:
    def __init__(self, binding, limits):
        self.binding, self.limits = binding, limits

    def _exchange(self, operation, request=None):
        if not self.binding.store.is_dir():
            raise ProviderError('unavailable', 'published code store unavailable')
        payload = canonical_bytes({'operation': operation, 'request': request}) + b'\n'
        if len(payload) > self.limits.max_bytes:
            raise ProviderError('invalid', 'code request exceeded budget')
        command = [str(self.binding.python), '-m', 'engineer_context.knowitall',
                   '--store', str(self.binding.store), '--max-bytes', str(self.limits.max_bytes)]
        try:
            with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL) as process:
                try:
                    process.stdin.write(payload); process.stdin.close()
                    output = bytearray(); deadline = time.monotonic() + self.limits.timeout_seconds
                    with selectors.DefaultSelector() as selector:
                        selector.register(process.stdout, selectors.EVENT_READ)
                        while True:
                            remaining = deadline - time.monotonic()
                            if remaining <= 0 or not selector.select(remaining): raise ValueError()
                            part = os.read(process.stdout.fileno(), min(65536, self.limits.max_bytes + 1 - len(output)))
                            if not part: break
                            output.extend(part)
                            if len(output) > self.limits.max_bytes: raise ValueError()
                    if process.wait(timeout=max(.01, deadline-time.monotonic())) != 0: raise ValueError()
                    value = json.loads(output)
                    if not isinstance(value, dict) or value.get('error'): raise ValueError()
                    canonical_bytes(value)
                    return value
                finally:
                    if process.poll() is None:
                        process.kill(); process.wait()
        except Exception:
            raise ProviderError('unavailable', 'Knowitall transport failed or exceeded budget') from None

    def describe(self):
        info = self._exchange('describe')
        if info != {'contract': 'knowitall.code-context/v1', 'package_version': '0.1.0'}:
            raise ProviderError('unavailable', 'unsupported Knowitall contract')
        return {**info, 'identity_kind': 'provider-asserted',
                'binding': {k: str(v) for k,v in asdict(self.binding).items()}}

    def query(self, request):
        if request.get('project_id') != self.binding.project_id or request.get('repository_id') != self.binding.repository_id:
            raise ProviderError('invalid', 'code request binding mismatch')
        return self._exchange('query', request)


def bridge_main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--store', required=True, type=Path)
    parser.add_argument('--max-bytes', required=True, type=int)
    args = parser.parse_args(argv)
    try:
        if version('knowitall-code-context') != '0.1.0' or not args.store.is_dir(): raise ValueError()
        line = sys.stdin.buffer.readline(args.max_bytes + 1)
        if len(line) > args.max_bytes or not line.endswith(b'\n'): raise ValueError()
        value = json.loads(line)
        if value['operation'] == 'describe':
            result = {'contract': 'knowitall.code-context/v1', 'package_version': '0.1.0'}
        elif value['operation'] == 'query':
            from knowitall_contract.validation import validate_query_request
            from knowitall_publication.store import PublicationStore
            from knowitall_query.service import QueryService
            request = value['request']; validate_query_request(request)
            result = QueryService(PublicationStore(args.store)).execute(request)
            validate_response(request, result)
        else: raise ValueError()
        output = canonical_bytes(result) + b'\n'
        if len(output) > args.max_bytes: raise ValueError()
        sys.stdout.buffer.write(output); return 0
    except Exception:
        sys.stdout.write('{"error":"code provider unavailable or invalid"}\n'); return 1


if __name__ == '__main__':
    raise SystemExit(bridge_main())
