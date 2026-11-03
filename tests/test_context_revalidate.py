import copy
import unittest
from engineer_context.config import parse_task
from engineer_context.collect import collect_with_clients
from engineer_context.revalidate import revalidate_with_clients
from test_context_collect import CONFIG, BUSINESS, BusinessClient, collection_request
from test_context_config import TASK

class ChangedBusiness(BusinessClient):
    async def get(self, locator):
        value=copy.deepcopy(BUSINESS); value['handling']=['new restriction']; return value

class ChangedBinding(BusinessClient):
    async def describe(self): return {'binding':{'project_id':'other'},'identity_kind':'configured'}

class RevalidateTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.packet=await collect_with_clients(CONFIG,collection_request(),BusinessClient())

    async def test_unchanged_evidence_revalidates_ready(self):
        before=copy.deepcopy(self.packet)
        result=await revalidate_with_clients(CONFIG,self.packet,parse_task(TASK),BusinessClient())
        self.assertEqual(result['readiness'],'ready')
        self.assertEqual(result['packet_digest'],self.packet['digest'])
        self.assertEqual(result['task'],TASK)
        self.assertEqual(self.packet,before)

    async def test_handling_or_qualification_change_blocks_unchanged_text(self):
        result=await revalidate_with_clients(CONFIG,self.packet,parse_task(TASK),ChangedBusiness())
        self.assertEqual(result['readiness'],'blocked')
        self.assertEqual(result['checks'][0]['status'],'changed')

    async def test_wrong_handoff_or_tampered_digest_is_rejected(self):
        with self.assertRaises(ValueError):
            await revalidate_with_clients(CONFIG,self.packet,parse_task(dict(TASK,workspace_id='wrong')),BusinessClient())
        self.packet['business'][0]['response']['handling']=[]
        with self.assertRaises(ValueError):
            await revalidate_with_clients(CONFIG,self.packet,parse_task(TASK),BusinessClient())

    async def test_changed_binding_or_failed_required_provider_blocks(self):
        for client in [ChangedBinding(),BusinessClient(True)]:
            result=await revalidate_with_clients(CONFIG,self.packet,parse_task(TASK),client)
            self.assertEqual(result['readiness'],'blocked')
