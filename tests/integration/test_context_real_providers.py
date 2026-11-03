"""Opt-in actual provider acceptance; missing prerequisites fail, never skip.

Set ENGINEER_LIBRARIAN_SOURCE to an explicitly verified owning source path.
Only temporary non-identifying source is processed.
"""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from engineer_context.collect import collect
from engineer_context.config import ConsumerConfig,LibrarianBinding,Limits,parse_task
from engineer_context.packet import validate_packet
from engineer_context.revalidate import revalidate

TASK={'daemon_id':'local','project_uid':'component-project','issue_uid':'component-task','workspace_id':'component-workspace'}


def command(args,cwd=None):
    return subprocess.run(args,cwd=cwd,check=True,capture_output=True,text=True,timeout=60).stdout


def create_fixture(root):
    librarian=Path(os.environ['ENGINEER_LIBRARIAN_SOURCE']).resolve()
    # Use supported Librarian release selection rather than its populated corpus.
    script='import sys,shutil;from pathlib import Path;sys.path.insert(0,sys.argv[1]);import package;root=Path(sys.argv[2]);dest=Path(sys.argv[3]);[( (dest/name).parent.mkdir(parents=True,exist_ok=True),shutil.copyfile(source,dest/name)) for name,source in package.release_paths(root)]'
    corpus=root/'corpus'
    command([sys.executable,'-c',script,str(librarian/'tools'),str(librarian),str(corpus)])
    (corpus/'documents').mkdir(exist_ok=True)
    document=corpus/'documents/guide.md'; document.write_text('# Guide\n\n## Overview\n\nComponent-owned qualified requirement.\n')
    selection={'schema_version':1,'audience':'authorized-local','documents':[{'path':'documents/guide.md','role':'toolkit-documentation','context':[]}],'context_rules':{},'renditions':[]}
    (corpus/'config/selection.json').write_text(json.dumps(selection))
    command([sys.executable,str(corpus/'tools/initialize.py')])
    executable=root/'librarian-mcp'
    # Local runtime entry point for actual owning MCP, never a test provider.
    executable.write_text(f'#!{sys.executable}\nimport sys\nsys.path.insert(0,{str(librarian/"tools/context-mcp/src")!r})\nfrom the_librarian_mcp.server import main\nmain()\n'); executable.chmod(0o700)
    config=ConsumerConfig(LibrarianBinding('business-component',executable,corpus),Limits())
    request={'task':TASK.copy(),'business':[{'locator':'documents/guide.md#overview','required':True}]}
    return config,request,document


class RealProviders(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.assertTrue(os.environ.get('ENGINEER_LIBRARIAN_SOURCE'),'explicit prerequisite missing: ENGINEER_LIBRARIAN_SOURCE')
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.config,self.request,self.document=await asyncio.to_thread(create_fixture,Path(self.temp.name))

    async def test_real_qualified_read_handoff(self):
        packet=await collect(self.config,self.request);validate_packet(packet,parse_task(TASK))
        self.assertEqual(packet['readiness'],'ready')
        self.assertIn('Component-owned qualified requirement.',str(packet['business'][0]['response']))
        handoff=json.loads(json.dumps(packet));validate_packet(handoff,parse_task(TASK))
        validation=await revalidate(self.config,handoff,parse_task(TASK))
        self.assertEqual(validation['readiness'],'ready')

    async def test_real_source_correction_blocks(self):
        packet=await collect(self.config,self.request)
        self.document.write_text(self.document.read_text()+'\nCorrected qualification.\n')
        result=await revalidate(self.config,packet,parse_task(TASK))
        self.assertEqual(result['readiness'],'blocked')
        self.assertTrue(any(c['provider']=='librarian' and c['status']!='unchanged' for c in result['checks']))


if __name__=='__main__': unittest.main()
