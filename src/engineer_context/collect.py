"""Compose scoped business observations for one task and workspace."""
from contextlib import AsyncExitStack
import copy
from datetime import datetime, timezone
import uuid
from .config import exact_fields, identity, parse_task
from .librarian import LibrarianClient, ProviderError
from .packet import SCHEMA, canonical_bytes, seal_packet


def now():
    return datetime.now(timezone.utc).isoformat()


def validate_collection(config, request):
    exact_fields(request, ['task', 'business'], ['run_ref'])
    parse_task(request['task'])
    if request.get('run_ref') is not None: identity(request['run_ref'])
    if len(canonical_bytes(request)) > config.limits.max_bytes:
        raise ValueError('collection request exceeded budget')
    items=request['business']
    if not isinstance(items,list) or len(items)>config.limits.max_business_locators: raise ValueError('invalid collection scope')
    for item in items:
        exact_fields(item, ['locator','required'])
        if type(item['required']) is not bool: raise ValueError('required must be boolean')
        identity(item['locator'])


class UnavailableClient:
    def __init__(self, error): self.error=error
    async def describe(self): raise self.error
    async def status(self): raise self.error
    async def get(self, locator): raise self.error


async def collect(config, request):
    validate_collection(config,request)
    # Only initialization errors may become scoped observations; caller errors
    # or composition failures must not cause a second provider collection.
    async with AsyncExitStack() as stack:
        try:
            business=await stack.enter_async_context(LibrarianClient.open(config.librarian,config.limits))
        except ProviderError as error:
            business=UnavailableClient(error)
        return await collect_with_clients(config,request,business)


async def collect_with_clients(config, request, librarian):
    validate_collection(config,request)
    request=copy.deepcopy(request)
    packet=dict(schema=SCHEMA, packet_id=str(uuid.uuid4()), observed_at=now(),
                task=request['task'],run_ref=request.get('run_ref'),providers={},business=[],
                capabilities={'assertions': {'status':'unavailable','owner':'the_librarian#923h'},
                              'contributions': {'status':'unavailable','owner':'the_librarian#rjr5'}},issues=[],readiness='ready')

    business_error=None
    try:
        description=await librarian.describe(); status=await librarian.status()
        if status.get('fresh') is not True: raise ProviderError('stale','business context not fresh')
        packet['providers']['librarian']={'description':description,'status':status}
    except ProviderError as error:
        business_error=error
        packet['providers']['librarian']={'description':None,'status':error.status}
    for index,item in enumerate(request['business']):
        entry=dict(request={'locator':item['locator']},required=item['required'],response=None)
        try:
            if business_error: raise business_error
            entry['response']=await librarian.get(item['locator'])
        except ProviderError as error:
            packet['issues'].append(dict(provider='librarian',scope=index,required=item['required'],status=error.status,reason=error.reason))
            if item['required']: packet['readiness']='blocked'
        packet['business'].append(entry)
    sealed=seal_packet(packet)
    if len(canonical_bytes(sealed))>config.limits.max_bytes: raise ValueError('packet exceeded budget; narrow scope')
    return sealed
