import copy
import json
from pathlib import Path
import unittest
from engineer_context.config import ConsumerConfig, LibrarianBinding, KnowitallBinding, Limits
from engineer_context.collect import collect_with_clients
from engineer_context.errors import InvalidCodeRequest
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

def paging_token(query):
    """Mirror the fake provider's selector-and-query-bound page token."""
    return 'token:'+query['selector']['mode']+':'+json.dumps(query['query'],sort_keys=True)


class PagingClient(CodeClient):
    """Two real pages per paged query: a token binds the selector that issued it."""
    def __init__(self, value=None, only=None):
        super().__init__(value); self.only=only
    def token(self, req): return paging_token(req)
    def query(self, req):
        held=req.get('continuation')
        if held is not None and held!=self.token(req): raise ProviderError('invalid','request rejected')
        result=super().query(req)
        paged=self.only is None or req['query']==self.only
        if held is None and paged: result['continuation']=self.token(req); result['truncated']=True
        return result

class RejectingClient(CodeClient):
    """Stands in for the owning contract refusing a malformed request."""
    def query(self, req): raise InvalidCodeRequest('code request rejected by the owning contract')

class Unreachable(CodeClient):
    """Proves the consumer refuses invalid scope without contacting a provider."""
    def describe(self): raise AssertionError('provider contacted for an invalid request')
    def query(self, req): raise AssertionError('provider contacted for an invalid request')

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
        second['request']['continuation']=paging_token(second['request']); req['code'].append(second)
        packet=await collect_with_clients(CONFIG,req,BusinessClient(),PagingClient())
        self.assertEqual(packet['code'][1]['request']['selector'],{'mode':'current'})
        self.assertIsNotNone(packet['code'][1]['response'])
        self.assertEqual(packet['readiness'],'ready')
        self.assertEqual([issue for issue in packet['issues'] if issue['provider']=='knowitall'],[])

    async def test_page_chain_after_another_current_query_stays_whole(self):
        # Every page of a supplied chain keeps the selector that bound its
        # tokens, even when an earlier current query already pinned the
        # generation; identity is checked against that pin afterwards.
        req=collection_request(); req['code'][0]['request']['selector']={'mode':'current'}
        first=copy.deepcopy(req['code'][0]); first['request']['request_id']='paged'
        first['request']['query']={'kind':'path','path':'src/wide.py'}
        second=copy.deepcopy(first); second['request']['request_id']='paged-2'
        second['request']['continuation']=paging_token(first['request'])
        req['code'].extend([first,second])
        packet=await collect_with_clients(CONFIG,req,BusinessClient(),PagingClient(only=first['request']['query']))
        self.assertEqual(packet['code'][1]['request']['selector'],{'mode':'current'})
        self.assertEqual(packet['readiness'],'ready')
        self.assertEqual([issue for issue in packet['issues'] if issue['provider']=='knowitall'],[])

    async def test_page_without_the_rest_of_its_chain_blocks(self):
        req=collection_request(); req['code'][0]['request']['selector']={'mode':'current'}
        req['code'][0]['request']['continuation']=paging_token(req['code'][0]['request'])
        packet=await collect_with_clients(CONFIG,req,BusinessClient(),PagingClient())
        self.assertEqual(packet['readiness'],'blocked')
        self.assertIsNotNone(packet['code'][0]['response'])
        self.assertEqual([issue['reason'] for issue in packet['issues'] if issue['provider']=='knowitall'],
                         ['other pages of this code query are absent'])

    async def test_outgoing_page_without_its_successor_blocks(self):
        req=collection_request(); req['code'][0]['request']['selector']={'mode':'current'}
        packet=await collect_with_clients(CONFIG,req,BusinessClient(),PagingClient())
        self.assertEqual(packet['readiness'],'blocked')
        self.assertEqual([issue['reason'] for issue in packet['issues'] if issue['provider']=='knowitall'],
                         ['other pages of this code query are absent'])

    async def test_rejected_request_is_caller_input_not_a_provider_gap(self):
        for required in [True,False]:
            req=collection_request(); req['code'][0]['required']=required
            with self.assertRaises(InvalidCodeRequest):
                await collect_with_clients(CONFIG,req,BusinessClient(),RejectingClient())

    async def test_incomplete_code_request_is_refused_before_any_provider_call(self):
        cases={'missing query':lambda q:q.pop('query'),'missing contract':lambda q:q.pop('contract'),
               'wrong contract':lambda q:q.__setitem__('contract','other/v1'),
               'missing request_id':lambda q:q.pop('request_id'),
               'unknown field':lambda q:q.__setitem__('extra',1),
               'exact without generation':lambda q:q['selector'].pop('generation_id'),
               'query without kind':lambda q:q.__setitem__('query',{'name':'submit_order'}),
               'empty continuation':lambda q:q.__setitem__('continuation',''),
               'unsupported match':lambda q:q.__setitem__('query',{'kind':'symbol','name':'submit_order','match':'fuzzy'}),
               'non-string name':lambda q:q.__setitem__('query',{'kind':'symbol','name':7,'match':'exact'}),
               'unsupported direction':lambda q:q.__setitem__('query',{'kind':'dependencies','symbol_id':'s','direction':'both','relationship_kinds':['calls']}),
               'empty relationship kinds':lambda q:q.__setitem__('query',{'kind':'dependencies','symbol_id':'s','direction':'outgoing','relationship_kinds':[]}),
               'repeated relationship kinds':lambda q:q.__setitem__('query',{'kind':'dependencies','symbol_id':'s','direction':'outgoing','relationship_kinds':['calls','calls']}),
               'escaping path':lambda q:q.__setitem__('query',{'kind':'path','path':'../outside.py'}),
               'absolute path':lambda q:q.__setitem__('query',{'kind':'path','path':'/etc/passwd'}),
               'zero line':lambda q:q.__setitem__('query',{'kind':'source_range','path':'src/orders.py','start':{'line':0,'column':1},'end':{'line':2,'column':1}}),
               'boolean line':lambda q:q.__setitem__('query',{'kind':'source_range','path':'src/orders.py','start':{'line':True,'column':1},'end':{'line':2,'column':1}}),
               'position without column':lambda q:q.__setitem__('query',{'kind':'source_range','path':'src/orders.py','start':{'line':1},'end':{'line':2,'column':1}}),
               'empty range':lambda q:q.__setitem__('query',{'kind':'source_range','path':'src/orders.py','start':{'line':3,'column':4},'end':{'line':3,'column':4}}),
               'reversed range':lambda q:q.__setitem__('query',{'kind':'source_range','path':'src/orders.py','start':{'line':9,'column':1},'end':{'line':2,'column':1}}),
               'unhashable relationship kind':lambda q:q.__setitem__('query',{'kind':'dependencies','symbol_id':'s','direction':'outgoing','relationship_kinds':[{'kind':'calls'}]}),
               'unhashable selector mode':lambda q:q.__setitem__('selector',{'mode':[]}),
               'unhashable query kind':lambda q:q.__setitem__('query',{'kind':{}})}
        for name,break_it in cases.items():
            for required in [True,False]:
                with self.subTest(case=name,required=required):
                    req=collection_request(); req['code'][0]['required']=required; break_it(req['code'][0]['request'])
                    # An unreachable provider must not turn caller input into an
                    # availability gap that a ready packet could hide.
                    with self.assertRaises(ValueError):
                        await collect_with_clients(CONFIG,req,BusinessClient(),Unreachable())

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
