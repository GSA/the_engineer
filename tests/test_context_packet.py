"""Dropping provenance or accepting a tampered handoff is a consumer bug."""
import copy
import json
import unittest
from engineer_context.config import parse_task
from engineer_context.packet import seal_packet, validate_packet
from test_context_config import TASK


def packet_value():
    return dict(schema='engineer.task-context/v1', packet_id='packet-1', observed_at='2026-10-29T00:00:00Z',
                task=TASK.copy(), run_ref=None, providers={},
                business=[dict(request={'locator': 'doc:1'}, required=True, response={'handling': ['restricted'], 'pieces': [dict(locator='doc:1', path='doc.md', source_hash='abc', line_start=1, line_end=2, text='Exact\npassage', reasons=['qualified'])]})],
                code=[dict(request={}, required=True, response={'range': dict(path='code.py', line_start=3, line_end=4), 'snapshot': 's1'})],
                associations=[], capabilities={'assertions': {'status': 'unavailable'}, 'contributions': {'status': 'unavailable'}}, issues=[], readiness='ready')

class PacketTests(unittest.TestCase):
    def test_packet_round_trip_retains_exact_passage_and_range(self):
        original = packet_value(); before = copy.deepcopy(original)
        sealed = seal_packet(original); decoded = json.loads(json.dumps(sealed))
        validate_packet(decoded, parse_task(TASK))
        self.assertEqual(decoded['business'][0]['response']['pieces'][0]['text'], 'Exact\npassage')
        self.assertEqual(decoded['business'][0]['response']['handling'], ['restricted'])
        self.assertEqual(decoded['code'][0]['response']['range'], {'path': 'code.py', 'line_start': 3, 'line_end': 4})
        self.assertEqual(original, before)

    def test_packet_digest_detects_mutation(self):
        sealed = seal_packet(packet_value()); sealed['business'][0]['response']['handling'] = []
        with self.assertRaises(ValueError): validate_packet(sealed)

    def test_handoff_rejects_wrong_task_or_workspace(self):
        sealed = seal_packet(packet_value())
        for field in TASK:
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_packet(sealed, parse_task(dict(TASK, **{field: 'other'})))

    def test_malformed_packet_is_not_sealable(self):
        for field, value in [('schema', 'unknown'), ('business', {}), ('readiness', 'maybe'), ('observed_at', float('nan'))]:
            packet = packet_value(); packet[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): seal_packet(packet)
