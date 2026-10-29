"""Read-only bridge into an explicitly installed owning query implementation."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import selectors
import subprocess
import time
from .bridge import REASONS, canonical, check_response, published_store
from .errors import InvalidCodeRequest, ProviderError

BRIDGE = Path(__file__).with_name('bridge.py')


def validate_response(request, response):
    try:
        check_response(request, response)
    except Exception:
        raise ProviderError('invalid', 'Knowitall contract or identity validation failed') from None


class KnowitallClient:
    def __init__(self, binding, limits):
        self.binding, self.limits = binding, limits

    def _exchange(self, operation, request=None):
        if not published_store(self.binding.store):
            raise ProviderError('unavailable', REASONS['store-unavailable'])
        payload = canonical({'operation': operation, 'request': request}) + b'\n'
        if len(payload) > self.limits.max_bytes:
            raise ProviderError('invalid', 'code request exceeded budget')
        # The bridge runs by path: the provider interpreter owns the Knowitall
        # packages and need not have this consumer installed.
        command = [str(self.binding.python), str(BRIDGE),
                   '--store', str(self.binding.store), '--max-bytes', str(self.limits.max_bytes)]
        try:
            with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL) as process:
                try:
                    deadline = time.monotonic() + self.limits.timeout_seconds
                    output = bytearray()
                    # Delivery shares the deadline: a runtime that never reads must not
                    # block this consumer on a full pipe.
                    os.set_blocking(process.stdin.fileno(), False)
                    with selectors.DefaultSelector() as selector:
                        selector.register(process.stdin, selectors.EVENT_WRITE)
                        selector.register(process.stdout, selectors.EVENT_READ)
                        sent = 0
                        while True:
                            remaining = deadline - time.monotonic()
                            ready = selector.select(remaining) if remaining > 0 else []
                            if not ready: raise ValueError()
                            for key, _ in ready:
                                if key.fileobj is process.stdin:
                                    sent += os.write(process.stdin.fileno(), payload[sent:])
                                    if sent == len(payload):
                                        selector.unregister(process.stdin); process.stdin.close()
                                else:
                                    part = os.read(process.stdout.fileno(),
                                                   min(65536, self.limits.max_bytes + 1 - len(output)))
                                    if not part:
                                        if sent != len(payload): raise ValueError()
                                        selector.unregister(process.stdout)
                                    output.extend(part)
                                    if len(output) > self.limits.max_bytes: raise ValueError()
                            if not selector.get_map(): break
                    status = process.wait(timeout=max(.01, deadline-time.monotonic()))
                    value = json.loads(output)
                    if not isinstance(value, dict): raise ValueError()
                    if status != 0 or value.get('error'):
                        reason = value.get('error')
                        # A rejected request is a caller mistake, not a provider gap, so it
                        # must not be recorded as a scoped availability observation.
                        if reason == 'request-invalid': raise InvalidCodeRequest(REASONS[reason])
                        raise ProviderError('unavailable', REASONS.get(reason, 'Knowitall exchange failed'))
                    canonical(value)
                    return value
                finally:
                    if process.poll() is None:
                        process.kill(); process.wait()
        except ProviderError:
            raise
        except InvalidCodeRequest:
            raise
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
