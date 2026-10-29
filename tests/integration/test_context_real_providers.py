"""Opt-in actual provider acceptance; missing prerequisites fail, never skip.

Set ENGINEER_LIBRARIAN_SOURCE, ENGINEER_KNOWITALL_SOURCE and
KNOWITALL_GRAPHIFY_RUNTIME to explicitly verified owning runtime/source paths.
Only temporary non-identifying source is processed.
"""
import asyncio
from dataclasses import asdict
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from engineer_context.collect import collect
from engineer_context.config import ConsumerConfig,LibrarianBinding,KnowitallBinding,Limits,parse_task
from engineer_context.packet import validate_packet
from engineer_context.revalidate import revalidate
from engineer_context.storage import write_private_json

TASK={'daemon_id':'local','project_uid':'component-project','issue_uid':'component-task','workspace_id':'component-workspace'}


def command(args,cwd=None):
    return subprocess.run(args,cwd=cwd,check=True,capture_output=True,text=True,timeout=60).stdout


def create_fixture(root):
    librarian=Path(os.environ['ENGINEER_LIBRARIAN_SOURCE']).resolve()
    knowitall=Path(os.environ['ENGINEER_KNOWITALL_SOURCE']).resolve()
    runtime=Path(os.environ['KNOWITALL_GRAPHIFY_RUNTIME']).resolve()
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
    repo=root/'repo'; shutil.copytree(knowitall/'tests/fixtures/repos/python_service',repo)
    # Enough same-named symbols that the owning page size must be exceeded, so
    # continuation is exercised against real extraction rather than a fixture.
    handlers=repo/'src/handlers'; handlers.mkdir()
    for index in range(101): (handlers/f'h{index}.py').write_text(f'def handle():\n    return {index}\n')
    # One file with more definitions than the owning page size, so a complete
    # final page of ok evidence is reachable.
    (repo/'src/wide.py').write_text(''.join(f'def wide{index}():\n    return {index}\n' for index in range(150)))
    for args in [['init','-q'],['config','user.name','Component Test'],['config','user.email','component@example.invalid'],['add','.'],['commit','-qm','component']]:
        command(['git','-c','core.hooksPath=/dev/null',*args],repo)
    from knowitall_snapshot import SnapshotPolicy,create_snapshot
    from knowitall_graphify import GraphifyConfig,executable_digest,extract_generation
    from knowitall_publication import PublicationStore
    snapshot=create_snapshot(repo,'code-component','repo-component',root/'snapshots',SnapshotPolicy())
    interpreter=runtime/'bin/python'
    package_root=runtime/'lib'/f'python{sys.version_info.major}.{sys.version_info.minor}'/'site-packages'
    generation=extract_generation(snapshot,root/'snapshots'/snapshot.snapshot_id/'source',root/'extraction',
                                  GraphifyConfig(executable=interpreter,python_path=str(package_root),expected_executable_digest=executable_digest(interpreter)))
    store=PublicationStore(root/'store'); store.publish(store.stage(generation))
    nodes={node.symbol_id:node for node in generation.nodes}
    edge=next(edge for edge in generation.edges if edge.kind=='calls' and nodes[edge.source].name=='submit_order()')
    query={'contract':'knowitall.code-context/v1','request_id':'component-query','project_id':'code-component','repository_id':'repo-component',
           'selector':{'mode':'exact','snapshot_id':snapshot.snapshot_id,'generation_id':generation.generation_id,'freshness':'require_current'},
           'query':{'kind':'dependencies','symbol_id':edge.source,'direction':'outgoing','relationship_kinds':['calls']}}
    config=ConsumerConfig(LibrarianBinding('business-component',executable,corpus/'tools/context-index/context_index.py',corpus),
                          KnowitallBinding('code-component','repo-component',Path(sys.executable),root/'store'),Limits())
    paging=dict(query,request_id='component-paging',query={'kind':'symbol','name':'handle()','match':'exact'})
    wide=dict(query,request_id='component-wide',query={'kind':'path','path':'src/wide.py'})
    request={'task':TASK.copy(),'business':[{'locator':'documents/guide.md#overview','required':True}],'code':[{'request':query,'required':True}]}
    return config,request,paging,wide,snapshot,generation,document


class RealProviders(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        for key in ['ENGINEER_LIBRARIAN_SOURCE','ENGINEER_KNOWITALL_SOURCE','KNOWITALL_GRAPHIFY_RUNTIME']:
            self.assertTrue(os.environ.get(key),f'explicit prerequisite missing: {key}')
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.config,self.request,self.paging,self.wide,self.snapshot,self.generation,self.document=await asyncio.to_thread(create_fixture,self.root)

    async def collect_code(self,query):
        return await collect(self.config,{'task':TASK.copy(),'business':[],'code':[{'request':query,'required':True}]})

    async def final_page(self,selector):
        """Walk real pages with held tokens until the complete last page."""
        query=dict(self.wide,selector=selector); pages=0
        while True:
            packet=await self.collect_code(query); page=packet['code'][0]['response']
            self.assertEqual(page['status'],'ok'); pages+=1
            if not page['truncated']: break
            query=dict(self.wide,selector=selector,continuation=page['continuation'])
        self.assertGreater(pages,1)
        return packet

    async def page_chain(self,selector):
        """Collect every page of one real paged query into a single packet."""
        scope=[{'request':dict(self.wide,selector=selector),'required':True}]
        while True:
            packet=await collect(self.config,{'task':TASK.copy(),'business':[],'code':scope})
            page=packet['code'][-1]['response']
            self.assertEqual(page['status'],'ok')
            if not page['truncated']: return packet
            scope=[{'request':dict(entry['request']),'required':True} for entry in packet['code']]
            scope.append({'request':dict(self.wide,selector=selector,continuation=page['continuation']),'required':True})

    async def test_real_held_page_follows_a_current_query_in_one_collection(self):
        first=await self.collect_code(dict(self.wide,selector={'mode':'current'}))
        token=first['code'][0]['response']['continuation']
        self.assertIsNotNone(token)
        packet=await collect(self.config,{'task':TASK.copy(),'business':[],'code':[
            {'request':dict(self.wide,request_id='component-current',selector={'mode':'current'}),'required':True},
            {'request':dict(self.wide,selector={'mode':'current'},continuation=token),'required':True}]})
        held=packet['code'][1]
        self.assertEqual(held['request']['selector'],{'mode':'current'})
        self.assertIsNotNone(held['response'])
        self.assertEqual(held['response']['status'],'ok')
        self.assertEqual(held['response']['resolved']['generation_id'],self.generation.generation_id)

    async def test_real_malformed_code_request_is_invalid_input(self):
        # The owning contract rejects it, so it is caller input, never an
        # optional availability gap that a ready packet could hide.
        broken=dict(self.wide); broken.pop('query')
        for required in [True,False]:
            with self.subTest(required=required):
                with self.assertRaises(ValueError):
                    await collect(self.config,{'task':TASK.copy(),'business':[],
                                               'code':[{'request':broken,'required':required}]})

    async def test_real_complete_page_chain_is_ready(self):
        packet=await self.page_chain({'mode':'current'})
        self.assertEqual(packet['readiness'],'ready')
        self.assertGreater(len(packet['code']),1)
        self.assertTrue(all(entry['response']['status']=='ok' for entry in packet['code']))
        result=await revalidate(self.config,packet,parse_task(TASK))
        self.assertEqual(result['readiness'],'ready')

    async def test_real_final_page_alone_is_blocked_but_revalidates(self):
        # A page token is bound to the selector that issued it, so revalidation
        # must recheck currency without rebinding the held token, and a packet
        # holding only the last page stays honest about the pages it lacks.
        for selector in [{'mode':'current'},dict(self.wide['selector'],freshness='allow_historical')]:
            with self.subTest(mode=selector['mode'],freshness=selector.get('freshness')):
                packet=await self.final_page(selector)
                self.assertEqual(packet['readiness'],'blocked')
                self.assertIn('other pages of this code query are absent',
                              [issue['reason'] for issue in packet['issues']])
                self.assertTrue(packet['code'][0]['response']['evidence'])
                self.assertIn('continuation',packet['code'][0]['request'])
                result=await revalidate(self.config,packet,parse_task(TASK))
                self.assertTrue(all(c['status']=='unchanged' for c in result['checks']))

    async def test_real_newer_publication_blocks_a_held_page_chain(self):
        packet=await self.page_chain({'mode':'current'})
        self.assertEqual(packet['readiness'],'ready')
        await asyncio.to_thread(self.publish_second_generation)
        result=await revalidate(self.config,packet,parse_task(TASK))
        self.assertEqual(result['readiness'],'blocked')
        self.assertTrue(any(c['provider']=='knowitall' and c['status']!='unchanged' for c in result['checks']))

    def publish_second_generation(self):
        from knowitall_snapshot import SnapshotPolicy,create_snapshot
        from knowitall_graphify import GraphifyConfig,executable_digest,extract_generation
        from knowitall_publication import PublicationStore
        repo=self.root/'repo'
        (repo/'revision.txt').write_text('second component revision\n')
        command(['git','add','.'],repo)
        command(['git','-c','core.hooksPath=/dev/null','commit','-qm','second component revision'],repo)
        snapshot=create_snapshot(repo,'code-component','repo-component',self.root/'snapshots',SnapshotPolicy())
        runtime=Path(os.environ['KNOWITALL_GRAPHIFY_RUNTIME'])
        interpreter=runtime/'bin/python'
        generation=extract_generation(snapshot,self.root/'snapshots'/snapshot.snapshot_id/'source',self.root/'extraction-2',
            GraphifyConfig(executable=interpreter,python_path=str(runtime/'lib'/f'python{sys.version_info.major}.{sys.version_info.minor}'/'site-packages'),expected_executable_digest=executable_digest(interpreter)))
        store=PublicationStore(self.root/'store');store.publish(store.stage(generation))
        return snapshot,generation

    async def test_real_continuation_returns_the_next_page(self):
        first=await collect(self.config,{'task':TASK.copy(),'business':[],'code':[{'request':self.paging,'required':True}]})
        page=first['code'][0]['response']
        self.assertTrue(page['truncated']); self.assertIsNotNone(page['continuation'])
        self.assertEqual(len(page['ambiguities']),100)
        following=dict(self.paging,continuation=page['continuation'])
        second=await collect(self.config,{'task':TASK.copy(),'business':[],'code':[{'request':following,'required':True}]})
        rest=second['code'][0]['response']
        self.assertEqual(rest['status'],'ambiguous')
        self.assertEqual(len(rest['ambiguities']),1)
        self.assertFalse(rest['truncated'])
        seen={item['symbol_id'] for item in page['ambiguities']}
        self.assertNotIn(rest['ambiguities'][0]['symbol_id'],seen)

    async def test_real_qualified_read_and_code_query_handoff(self):
        packet=await collect(self.config,self.request);validate_packet(packet,parse_task(TASK))
        self.assertIsNotNone(packet['business'][0]['response'])
        self.assertIn('Component-owned qualified requirement.',str(packet['business'][0]['response']))
        resolved=packet['code'][0]['response']['resolved']
        self.assertEqual(resolved['snapshot_id'],self.snapshot.snapshot_id)
        self.assertEqual(resolved['generation_id'],self.generation.generation_id)
        self.assertEqual(resolved['commit'],self.snapshot.commit)
        self.assertTrue(packet['code'][0]['response']['evidence'])
        self.assertEqual(packet['associations'],[{'business':0,'code':0,'status':'unasserted'}])
        handoff=json.loads(json.dumps(packet));validate_packet(handoff,parse_task(TASK))
        # Graphify may expose honest partial scope; readiness must preserve it.
        validation=await revalidate(self.config,handoff,parse_task(TASK))
        self.assertEqual(validation['readiness'],packet['readiness'])

    async def test_real_source_correction_and_generation_change_block(self):
        packet=await collect(self.config,self.request)
        self.document.write_text(self.document.read_text()+'\nCorrected qualification.\n')
        result=await revalidate(self.config,packet,parse_task(TASK))
        self.assertEqual(result['readiness'],'blocked')
        self.assertTrue(any(c['provider']=='librarian' and c['status']!='unchanged' for c in result['checks']))
        # Publish a second real extraction through the owning API. The old exact
        # selector must not silently follow this newer current generation.
        await asyncio.to_thread(self.publish_second_generation)
        result=await revalidate(self.config,packet,parse_task(TASK))
        self.assertTrue(any(c['provider']=='knowitall' and c['status']!='unchanged' for c in result['checks']))


if __name__=='__main__': unittest.main()
