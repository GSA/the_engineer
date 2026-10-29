import unittest
from engineer_context.report import render_report
from engineer_context.packet import seal_packet
from test_context_packet import packet_value

class ReportTests(unittest.TestCase):
    def test_report_has_exact_citations_and_no_asserted_link(self):
        value=packet_value(); value['associations']=[{'business':0,'code':0,'status':'unasserted'}]
        result=render_report(seal_packet(value))
        for text in ['doc:1','abc','Exact\npassage','code.py','unasserted','unavailable','public']:
            self.assertIn(text,result)
        self.assertNotIn('implements',result)
