from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from engineer_context.cli import main
from engineer_context.packet import seal_packet
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

    def test_report_does_not_contact_providers(self):
        self.path.write_text(json.dumps(seal_packet(packet_value())))
        with patch('engineer_context.cli.collect',side_effect=AssertionError('must not collect')),redirect_stdout(io.StringIO()):
            self.assertEqual(main(['report','--packet',str(self.path)]),0)
