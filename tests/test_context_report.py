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

    def test_rendition_piece_keeps_its_original_source_location(self):
        # Rendition pieces are indexed as extraction JSON, so a citation needs the
        # original location the provider reports, not just the indexed line range.
        value=packet_value()
        piece=value['business'][0]['response']['pieces'][0]
        piece.update(title='Attachment 2',role='reference-attachment',
                     source_location={'member':'word/document.xml','line':4120,'element':'w:p[18]'})
        result=render_report(seal_packet(value))
        for text in ['word/document.xml','4120','w:p[18]','Attachment 2','reference-attachment']:
            self.assertIn(text,result)
