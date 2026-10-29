"""Provider-environment bridge, runnable without this package installed.

The configured Knowitall interpreter owns the provider packages and need not
contain the consumer, so this file is launched by path and imports nothing from
`engineer_context`.
"""
import argparse
from importlib.metadata import version
import hashlib
import json
from pathlib import Path
import sys

CONTRACT = 'knowitall.code-context/v1'
PACKAGE_VERSION = '0.1.0'
# Fixed vocabulary: diagnoses the cause without echoing provider text.
REASONS = {'provider-missing': 'selected interpreter lacks knowitall-code-context 0.1.0',
           'store-unavailable': 'selected directory is not a published code store',
           'request-invalid': 'code request rejected by the owning contract',
           'response-invalid': 'code response failed owning contract or identity validation',
           'budget-exceeded': 'code exchange exceeded the selected byte budget'}


class BridgeError(Exception):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (TypeError, ValueError, UnicodeError) as error:
        raise ValueError('invalid JSON value') from error


def published_store(root):
    # The owning store constructor creates its layout, so an incomplete
    # directory is refused rather than written to by a read-only consumer.
    return all((Path(root) / name).is_dir() for name in ('stages', 'generations', 'current'))


def continuation_secret(root):
    """Derive a store-bound signing key so page cursors survive one exchange.

    Each exchange is a fresh process, and the owning service otherwise invents a
    random key, which would reject every continuation the previous response
    issued. Deriving the key from the store identity keeps cursors usable and
    grants nothing extra: a cursor only selects an offset within a binding the
    holder can already query directly.
    """
    return hashlib.sha256(b'engineer.task-context/v1 continuation\0' + str(Path(root).resolve()).encode()).digest()


def check_response(request, response):
    """Validate a response with the owning validator and the exact identity."""
    from knowitall_contract.validation import validate_query_request, validate_query_response
    validate_query_request(request)
    validate_query_response(response, expected_request=request)
    if request['selector']['mode'] == 'exact' and response.get('resolved') is not None:
        for field in ['snapshot_id', 'generation_id']:
            if response['resolved'][field] != request['selector'][field]:
                raise ValueError('exact selector resolved to another identity')


def rejected(response):
    """The owning service answers a refused request, including a cursor whose
    binding changed, with a valid response carrying this status. That is caller
    input rather than a gap in the provider's evidence."""
    return response.get('status') == 'invalid_request'


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--store', required=True, type=Path)
    parser.add_argument('--max-bytes', required=True, type=int)
    args = parser.parse_args(argv)
    try:
        try:
            if version('knowitall-code-context') != PACKAGE_VERSION: raise BridgeError('provider-missing')
        except Exception:
            raise BridgeError('provider-missing') from None
        if not published_store(args.store): raise BridgeError('store-unavailable')
        line = sys.stdin.buffer.readline(args.max_bytes + 1)
        if len(line) > args.max_bytes or not line.endswith(b'\n'): raise BridgeError('budget-exceeded')
        value = json.loads(line)
        if value['operation'] == 'describe':
            result = {'contract': CONTRACT, 'package_version': PACKAGE_VERSION}
        elif value['operation'] == 'query':
            from knowitall_contract.validation import validate_query_request
            from knowitall_publication.store import PublicationStore
            from knowitall_query.service import QueryService
            request = value['request']
            try: validate_query_request(request)
            except Exception: raise BridgeError('request-invalid') from None
            result = QueryService(PublicationStore(args.store),
                                  continuation_secret=continuation_secret(args.store)).execute(request)
            if rejected(result): raise BridgeError('request-invalid')
            try: check_response(request, result)
            except Exception: raise BridgeError('response-invalid') from None
        else: raise BridgeError('request-invalid')
        output = canonical(result) + b'\n'
        if len(output) > args.max_bytes: raise BridgeError('budget-exceeded')
        sys.stdout.buffer.write(output); return 0
    except BridgeError as error:
        sys.stdout.write(json.dumps({'error': error.reason}) + '\n'); return 1
    except Exception:
        sys.stdout.write(json.dumps({'error': 'response-invalid'}) + '\n'); return 1


if __name__ == '__main__':
    raise SystemExit(main())
