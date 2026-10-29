import json
import os
from pathlib import Path
import tempfile
import unittest
from engineer_context.storage import write_private_json, read_private_json

class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root=Path(self.temp.name)

    def test_atomic_private_output_roundtrip(self):
        path=self.root/'private'/'packet.json'
        write_private_json(path,{'text':'Exact\npassage'},1024)
        self.assertEqual(read_private_json(path,1024),{'text':'Exact\npassage'})
        self.assertEqual(path.stat().st_mode & 0o777,0o600)
        self.assertEqual(path.parent.stat().st_mode & 0o777,0o700)
        write_private_json(path,{'changed':True},1024)
        self.assertEqual(json.loads(path.read_text()),{'changed':True})

    def test_symlink_or_nonprivate_parent_is_refused(self):
        path=self.root/'packet'; path.symlink_to(self.root/'target')
        with self.assertRaises(ValueError): write_private_json(path,{},1024)
        public=self.root/'public'; public.mkdir(mode=0o755); public.chmod(0o755)
        with self.assertRaises(ValueError): write_private_json(public/'packet',{},1024)
        link=self.root/'link'; link.symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(ValueError): write_private_json(link/'packet',{},1024)
        self.assertEqual(public.stat().st_mode & 0o777,0o755)

    def test_oversized_output_leaves_no_partial_file(self):
        path=self.root/'packet'
        with self.assertRaises(ValueError): write_private_json(path,{'text':'x'*100},10)
        self.assertEqual(list(self.root.iterdir()),[])
