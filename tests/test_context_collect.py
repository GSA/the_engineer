import copy
from pathlib import Path
import unittest
from engineer_context.config import ConsumerConfig, LibrarianBinding, KnowitallBinding, Limits
from engineer_context.collect import collect_with_clients
from engineer_context.librarian import ProviderError
from engineer_context.packet import validate_packet
from test_context_config import TASK
from test_context_knowitall import request, response

CONFIG = ConsumerConfig(LibrarianBinding('business-1', Path('/bin/lib'), Path('/reader'), Path('/corpus')),
                        KnowitallBinding('project-synthetic', 'repo-python-service', Path('/bin/python'), Path('/store')), Limits())
BUSINESS = {'handling': ['private'], 'pieces': [{'locator':'doc.md#section', 'path':'doc.md', 'source_hash':'abc', 'line_start':1, 'line_end':1, 'text':'submit_order', 'reasons':['qualified']}]}

def collection_request():
    return dict(task=TASK.copy(), business=[dict(locator='doc.md#section', required=True)], code=[dict(request=request(), required=True)])

class BusinessClient:
    def __init__(self, fail=False): self.fail=fail
    async def describe(self): return {'binding': {'project_id':'business-1'}, 'identity_kind':'configured'}
    async def status(self):
        if self.fail: raise ProviderError('unavailable','provider absent')
        return {'fresh':True}
    async def get(self, locator): return copy.deepcopy(BUSINESS)

class CodeClient:
    def __init__(self, value=None): self.value=value or response()
    def describe(self): return {'binding': {'project_id':'project-synthetic', 'repository_id':'repo-python-service'}}
    def query(self, req):
        result=copy.deepcopy(self.value); result['request_id']=req['request_id']
        if req['selector']['mode']=='exact':
            # Reject substitution, so broken collection pinning cannot pass.
            if req['selector']['snapshot_id'] != result['resolved']['snapshot_id']: raise ProviderError('stale','changed')
        return result

class PagingClient(CodeClient):
    """Binds a page token to its selector, as the owning provider does."""
    def query(self, req):
        held=req.get('continuation')
        if held is not None and held!=f"token:{req['selector']['mode']}": raise ProviderError('invalid','request rejected')
        result=super().query(req); result['continuation']=f"token:{req['selector']['mode']}"; return result

class CollectTests(unittest.IsolatedAsyncioTestCase):
    async def test_collection_keeps_original_responses(self):
        req=collection_request(); before=copy.deepcopy(req)
        packet=await collect_with_clients(CONFIG,req,BusinessClient(),CodeClient())
        validate_packet(packet)
        self.assertEqual(packet['business'][0]['response'],BUSINESS)
        self.assertEqual(packet['code'][0]['response'],response())
        self.assertEqual(req,before)

    async def test_required_unavailable_blocks_optional_gap_does_not(self):
        req=collection_request()
        packet=await collect_with_clients(CONFIG,req,BusinessClient(True),CodeClient())
        self.assertEqual(packet['readiness'],'blocked')
        req['business'][0]['required']=False
        packet=await collect_with_clients(CONFIG,req,BusinessClient(True),CodeClient())
        self.assertEqual(packet['readiness'],'ready')
        self.assertIsNone(packet['business'][0]['response'])
        self.assertEqual(packet['issues'][0]['status'],'unavailable')

    async def test_current_is_pinned_for_followup_queries(self):
        req=collection_request(); req['code'][0]['request']['selector']={'mode':'current'}
        second=copy.deepcopy(req['code'][0]); second['request']['request_id']='followup'; req['code'].append(second)
        packet=await collect_with_clients(CONFIG,req,BusinessClient(),CodeClient())
        self.assertEqual(packet['code'][1]['request']['selector'], {'mode':'exact','snapshot_id':'snap-python-0001','generation_id':'gen-python-0001','freshness':'require_current'})
        self.assertEqual(packet['readiness'],'ready')

    async def test_held_continuation_keeps_the_selector_that_issued_it(self):
        req=collection_request(); req['code'][0]['request']['selector']={'mode':'current'}
        second=copy.deepcopy(req['code'][0]); second['request']['request_id']='followup'
        second['request']['continuation']='token:current'; req['code'].append(second)
        packet=await collect_with_clients(CONFIG,req,BusinessClient(),PagingClient())
        self.assertEqual(packet['code'][1]['request']['selector'],{'mode':'current'})
        self.assertIsNotNone(packet['code'][1]['response'])
        self.assertEqual([issue for issue in packet['issues'] if issue['provider']=='knowitall'
                          and issue['status'] not in ('partial','truncated')],[])

    async def test_name_match_never_creates_assertion(self):
        packet=await collect_with_clients(CONFIG,collection_request(),BusinessClient(),CodeClient())
        self.assertEqual(packet['associations'], [{'business':0,'code':0,'status':'unasserted'}])
        self.assertEqual(packet['capabilities']['assertions']['status'],'unavailable')
        self.assertEqual(packet['capabilities']['contributions']['status'],'unavailable')

    async def test_missing_side_creates_no_association(self):
        packet=await collect_with_clients(CONFIG,collection_request(),BusinessClient(True),CodeClient())
        self.assertEqual(packet['associations'],[])

    async def test_partial_required_scope_or_continuation_blocks_readiness(self):
        for updates in [dict(truncated=True,continuation='next'), dict(ambiguities=[{'x':'ambiguous'}]), dict(status='partial')]:
            result=response(); result.update(updates)
            packet=await collect_with_clients(CONFIG,collection_request(),BusinessClient(),CodeClient(result))
            self.assertEqual(packet['readiness'],'blocked')
            self.assertIsNotNone(packet['code'][0]['response'])

    async def test_wrong_binding_and_oversized_scope_are_rejected(self):
        req=collection_request(); req['code'][0]['request']['project_id']='other'
        with self.assertRaises(ValueError): await collect_with_clients(CONFIG,req,BusinessClient(),CodeClient())
        req=collection_request(); req['business']*=11
        with self.assertRaises(ValueError): await collect_with_clients(CONFIG,req,BusinessClient(),CodeClient())
