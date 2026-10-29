import copy
import unittest
from engineer_context.config import parse_task
from engineer_context.collect import collect_with_clients
from engineer_context.errors import InvalidCodeRequest
from engineer_context.revalidate import revalidate_with_clients
from test_context_collect import CONFIG, BUSINESS, BusinessClient, CodeClient, PagingClient, collection_request, paging_token
from test_context_config import TASK
from test_context_knowitall import response

class ChangedBusiness(BusinessClient):
    async def get(self, locator):
        value=copy.deepcopy(BUSINESS); value['handling']=['new restriction']; return value

class ChangedBinding(BusinessClient):
    async def describe(self): return {'binding':{'project_id':'other'},'identity_kind':'configured'}

class RejectingPages(PagingClient):
    """Currency probes succeed, but a held cursor's binding has changed."""
    def query(self, req):
        if req.get('continuation') is not None: raise InvalidCodeRequest('continuation rejected by the owning contract')
        return super().query(req)

class RevalidateTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.packet=await collect_with_clients(CONFIG,collection_request(),BusinessClient(),CodeClient())

    async def test_unchanged_evidence_revalidates_ready(self):
        before=copy.deepcopy(self.packet)
        result=await revalidate_with_clients(CONFIG,self.packet,parse_task(TASK),BusinessClient(),CodeClient())
        self.assertEqual(result['readiness'],'ready')
        self.assertEqual(result['packet_digest'],self.packet['digest'])
        self.assertEqual(result['task'],TASK)
        self.assertEqual(self.packet,before)

    async def test_handling_or_qualification_change_blocks_unchanged_text(self):
        result=await revalidate_with_clients(CONFIG,self.packet,parse_task(TASK),ChangedBusiness(),CodeClient())
        self.assertEqual(result['readiness'],'blocked')
        self.assertEqual(result['checks'][0]['status'],'changed')

    async def test_changed_generation_or_commit_blocks_without_substitution(self):
        for field in ['snapshot_id','generation_id','commit','content_manifest_digest','artifact_digest']:
            value=response(); value['resolved'][field]='different'
            result=await revalidate_with_clients(CONFIG,self.packet,parse_task(TASK),BusinessClient(),CodeClient(value))
            self.assertEqual(result['readiness'],'blocked',field)

    async def test_wrong_handoff_or_tampered_digest_is_rejected(self):
        with self.assertRaises(ValueError):
            await revalidate_with_clients(CONFIG,self.packet,parse_task(dict(TASK,workspace_id='wrong')),BusinessClient(),CodeClient())
        self.packet['business'][0]['response']['handling']=[]
        with self.assertRaises(ValueError):
            await revalidate_with_clients(CONFIG,self.packet,parse_task(TASK),BusinessClient(),CodeClient())

    async def test_rejected_held_continuation_blocks_with_a_receipt(self):
        # A newer publication between the currency probe and the replay makes
        # the provider refuse a cursor that was valid when collected; that is
        # changed provider state, so it must be reported, not raised.
        req=collection_request(); req['code'][0]['request']['selector']={'mode':'current'}
        second=copy.deepcopy(req['code'][0]); second['request']['request_id']='page-2'
        second['request']['continuation']=paging_token(req['code'][0]['request']); req['code'].append(second)
        packet=await collect_with_clients(CONFIG,req,BusinessClient(),PagingClient())
        self.assertEqual(packet['readiness'],'ready')
        result=await revalidate_with_clients(CONFIG,packet,parse_task(TASK),BusinessClient(),RejectingPages())
        self.assertEqual(result['readiness'],'blocked')
        held=[check for check in result['checks'] if check['provider']=='knowitall'][1]
        self.assertNotEqual(held['status'],'unchanged')

    async def test_changed_binding_or_failed_required_provider_blocks(self):
        for client in [ChangedBinding(),BusinessClient(True)]:
            result=await revalidate_with_clients(CONFIG,self.packet,parse_task(TASK),client,CodeClient())
            self.assertEqual(result['readiness'],'blocked')
