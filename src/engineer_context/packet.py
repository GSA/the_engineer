"""Lossless, digest-bound task handoffs (not signed attestations)."""
import copy
import hashlib
import json
from .config import exact_fields, identity, parse_task

SCHEMA = 'engineer.task-context/v1'
FIELDS = ['schema', 'packet_id', 'observed_at', 'task', 'run_ref', 'providers',
          'business', 'code', 'associations', 'capabilities', 'issues', 'readiness']


def canonical_bytes(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (TypeError, ValueError, UnicodeError) as error:
        raise ValueError('invalid JSON value') from error


def canonical_digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _shape(value):
    exact_fields(value, FIELDS)
    if value['schema'] != SCHEMA or value['readiness'] not in ('ready', 'blocked'):
        raise ValueError('invalid packet schema or readiness')
    identity(value['packet_id']); identity(value['observed_at']); parse_task(value['task'])
    if value['run_ref'] is not None:
        identity(value['run_ref'])
    for field in ['business', 'code', 'associations', 'issues']:
        if not isinstance(value[field], list):
            raise ValueError('invalid packet list')
    for field in ['providers', 'capabilities']:
        if not isinstance(value[field], dict):
            raise ValueError('invalid packet object')
    for entry in value['business'] + value['code']:
        exact_fields(entry, ['request', 'required', 'response'], ['diagnostics'])
        if not isinstance(entry['request'], dict) or type(entry['required']) is not bool or (entry['response'] is not None and not isinstance(entry['response'], dict)):
            raise ValueError('invalid evidence entry')
    canonical_bytes(value)


def seal_packet(value):
    result = copy.deepcopy(value)
    _shape(result)
    result['digest'] = canonical_digest(result)
    return result


def validate_packet(value, expected_task=None):
    if not isinstance(value, dict) or 'digest' not in value:
        raise ValueError('missing packet digest')
    body = {key: content for key, content in value.items() if key != 'digest'}
    _shape(body)
    if value['digest'] != canonical_digest(body):
        raise ValueError('packet digest mismatch')
    if expected_task is not None and parse_task(value['task']) != expected_task:
        raise ValueError('task or workspace mismatch')
