import copy
from pathlib import Path
import unittest
from engineer_context.config import ConsumerConfig, LibrarianBinding, Limits
from engineer_context.collect import collect_with_clients
from engineer_context.librarian import ProviderError
from engineer_context.packet import validate_packet
from test_context_config import TASK

CONFIG = ConsumerConfig(LibrarianBinding('business-1', Path('/bin/lib'), Path('/corpus')), Limits())
BUSINESS = {'handling': ['private'], 'pieces': [{'locator':'doc.md#section', 'path':'doc.md', 'source_hash':'abc', 'line_start':1, 'line_end':1, 'text':'submit_order', 'reasons':['qualified']}]}

def collection_request():
    return dict(task=TASK.copy(), business=[dict(locator='doc.md#section', required=True)])

class BusinessClient:
    def __init__(self, fail=False): self.fail=fail
    async def describe(self): return {'binding': {'project_id':'business-1'}, 'identity_kind':'configured'}
    async def status(self):
        if self.fail: raise ProviderError('unavailable','provider absent')
        return {'fresh':True}
    async def get(self, locator): return copy.deepcopy(BUSINESS)

class CollectTests(unittest.IsolatedAsyncioTestCase):
    async def test_collection_keeps_original_responses(self):
        req=collection_request(); before=copy.deepcopy(req)
        packet=await collect_with_clients(CONFIG,req,BusinessClient())
        validate_packet(packet)
        self.assertEqual(packet['schema'],'engineer.task-context/v2')
        self.assertEqual(packet['business'][0]['response'],BUSINESS)
        self.assertEqual(req,before)

    async def test_required_unavailable_blocks_optional_gap_does_not(self):
        req=collection_request()
        packet=await collect_with_clients(CONFIG,req,BusinessClient(True))
        self.assertEqual(packet['readiness'],'blocked')
        req['business'][0]['required']=False
        packet=await collect_with_clients(CONFIG,req,BusinessClient(True))
        self.assertEqual(packet['readiness'],'ready')
        self.assertIsNone(packet['business'][0]['response'])
        self.assertEqual(packet['issues'][0]['status'],'unavailable')

    async def test_capabilities_stay_unavailable(self):
        packet=await collect_with_clients(CONFIG,collection_request(),BusinessClient())
        self.assertEqual(packet['capabilities']['assertions']['status'],'unavailable')
        self.assertEqual(packet['capabilities']['contributions']['status'],'unavailable')

    async def test_retired_code_scope_and_oversized_scope_are_rejected(self):
        req=collection_request(); req['code']=[]
        with self.assertRaises(ValueError): await collect_with_clients(CONFIG,req,BusinessClient())
        req=collection_request(); req['business']*=11
        with self.assertRaises(ValueError): await collect_with_clients(CONFIG,req,BusinessClient())
