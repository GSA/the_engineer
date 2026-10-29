from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from engineer_context.cli import main
from engineer_context.packet import seal_packet
from test_context_config import TASK, config_value
from test_context_packet import packet_value

class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'packet.json'

    def test_cli_blocked_exit_is_distinct_from_invalid(self):
        value=packet_value(); value['readiness']='blocked'; self.path.write_text(json.dumps(seal_packet(value)))
        with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
            self.assertEqual(main(['report','--packet',str(self.path)]),2)
            self.path.write_text('{}')
            self.assertEqual(main(['report','--packet',str(self.path)]),1)

    def test_report_uses_the_configured_budget_for_large_packets(self):
        value=packet_value()
        value['business'][0]['response']['pieces'][0]['text']='x'*1200000
        self.path.write_text(json.dumps(seal_packet(value)))
        with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
            self.assertEqual(main(['report','--packet',str(self.path)]),1)
            self.assertEqual(main(['report','--packet',str(self.path),'--max-bytes','2000000']),0)

    def test_malformed_code_request_is_invalid_input_not_a_traceback(self):
        # A discriminator of the wrong JSON type must reach the documented
        # invalid-input exit, never an unhandled type error.
        config=self.path.parent/'config.json'; request=self.path.parent/'request.json'
        config.write_text(json.dumps(config_value()))
        value=dict(task=TASK.copy(),business=[],code=[dict(request=dict(
            contract='knowitall.code-context/v1',request_id='r1',project_id='code-1',repository_id='repo-1',
            selector={'mode':[]},query={'kind':'symbol','name':'submit_order','match':'exact'}),required=True)])
        request.write_text(json.dumps(value))
        for selector,query in [({'mode':[]},{'kind':'symbol','name':'submit_order','match':'exact'}),
                               ({'mode':'current'},{'kind':{}})]:
            value['code'][0]['request']['selector']=selector; value['code'][0]['request']['query']=query
            request.write_text(json.dumps(value))
            with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
                self.assertEqual(main(['collect','--config',str(config),'--request',str(request),
                                       '--output',str(self.path.parent/'packet.out')]),1)

    def test_report_does_not_contact_providers(self):
        self.path.write_text(json.dumps(seal_packet(packet_value())))
        with patch('engineer_context.cli.collect',side_effect=AssertionError('must not collect')),redirect_stdout(io.StringIO()):
            self.assertEqual(main(['report','--packet',str(self.path)]),0)
