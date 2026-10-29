"""Compose scoped observations; presentation is never an asserted link."""
import asyncio
import copy
from datetime import datetime, timezone
import uuid
from .config import exact_fields, identity, parse_task
from .knowitall import KnowitallClient
from .librarian import LibrarianClient, ProviderError
from .packet import canonical_bytes, seal_packet


def now():
    return datetime.now(timezone.utc).isoformat()


def validate_collection(config, request):
    exact_fields(request, ['task', 'business', 'code'], ['run_ref'])
    parse_task(request['task'])
    if request.get('run_ref') is not None: identity(request['run_ref'])
    if len(canonical_bytes(request)) > config.limits.max_bytes:
        raise ValueError('collection request exceeded budget')
    for name, ceiling in [('business',config.limits.max_business_locators),('code',config.limits.max_code_queries)]:
        items=request[name]
        if not isinstance(items,list) or len(items)>ceiling: raise ValueError('invalid collection scope')
        for item in items:
            exact_fields(item, ['locator' if name=='business' else 'request','required'])
            if type(item['required']) is not bool: raise ValueError('required must be boolean')
            if name=='business': identity(item['locator'])
            else:
                query=item['request']
                if not isinstance(query,dict) or query.get('project_id')!=config.knowitall.project_id or query.get('repository_id')!=config.knowitall.repository_id:
                    raise ValueError('code binding mismatch')
                selector=query.get('selector')
                if not isinstance(selector,dict) or selector.get('mode') not in ('exact','current'):
                    raise ValueError('invalid code selector')


def incomplete_code(response):
    return (response.get('status')!='ok' or bool(response.get('truncated')) or bool(response.get('continuation'))
            or bool(response.get('ambiguities')) or bool(response.get('missing_evidence'))
            or response.get('coverage',{}).get('relevant_scope')!='complete')


def pin_selector(resolved):
    return dict(mode='exact', snapshot_id=resolved['snapshot_id'], generation_id=resolved['generation_id'], freshness='require_current')


class UnavailableClient:
    def __init__(self, error): self.error=error
    async def describe(self): raise self.error
    async def status(self): raise self.error
    async def get(self, locator): raise self.error


async def collect(config, request):
    validate_collection(config,request)
    code=KnowitallClient(config.knowitall,config.limits)
    # Only initialization errors may become scoped observations; caller errors
    # or composition failures must not cause a second provider collection.
    from contextlib import AsyncExitStack
    async with AsyncExitStack() as stack:
        try:
            business=await stack.enter_async_context(LibrarianClient.open(config.librarian,config.limits))
        except ProviderError as error:
            business=UnavailableClient(error)
        return await collect_with_clients(config,request,business,code)


async def collect_with_clients(config, request, librarian, knowitall):
    validate_collection(config,request)
    request=copy.deepcopy(request)
    packet=dict(schema='engineer.task-context/v1', packet_id=str(uuid.uuid4()), observed_at=now(),
                task=request['task'],run_ref=request.get('run_ref'),providers={},business=[],code=[],associations=[],
                capabilities={'assertions': {'status':'unavailable','owner':'the_librarian#923h'},
                              'contributions': {'status':'unavailable','owner':'the_librarian#rjr5'}},issues=[],readiness='ready')

    def issue(provider, scope, required, error):
        packet['issues'].append(dict(provider=provider,scope=scope,required=required,status=error.status,reason=error.reason))
        if required: packet['readiness']='blocked'

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
        except ProviderError as error: issue('librarian',index,item['required'],error)
        packet['business'].append(entry)

    code_error=None
    try:
        packet['providers']['knowitall']={'description':await asyncio.to_thread(knowitall.describe)}
    except ProviderError as error:
        code_error=error; packet['providers']['knowitall']={'description':None,'status':error.status}
    pinned=None
    for index,item in enumerate(request['code']):
        query=item['request']
        held='continuation' in query
        # A held page token is bound to the selector that issued it, so it is
        # replayed unchanged and its identity is compared after the response.
        if query['selector']['mode']=='current' and pinned is not None and not held:
            query['selector']=pin_selector(pinned)
        entry=dict(request=query,required=item['required'],response=None)
        try:
            if code_error: raise code_error
            response=await asyncio.to_thread(knowitall.query,query)
            for field in ('project_id','repository_id','request_id','contract'):
                if response.get(field)!=query.get(field): raise ProviderError('invalid','code response identity mismatch')
            resolved=response.get('resolved')
            if resolved is not None and query['selector']['mode']=='exact':
                if any(resolved.get(field)!=query['selector'].get(field) for field in ('snapshot_id','generation_id')):
                    raise ProviderError('stale','exact code identity changed')
            if held and resolved is not None and pinned is not None:
                if any(resolved.get(field)!=pinned.get(field) for field in ('snapshot_id','generation_id')):
                    raise ProviderError('stale','continuation page left the pinned code generation')
            if query['selector']['mode']=='current' and resolved is not None and pinned is None: pinned=copy.deepcopy(resolved)
            entry['response']=response
            if incomplete_code(response): issue('knowitall',index,item['required'],ProviderError('partial','code scope incomplete'))
        except ProviderError as error: issue('knowitall',index,item['required'],error)
        packet['code'].append(entry)
    packet['associations']=[dict(business=b,code=c,status='unasserted')
                            for b,entry in enumerate(packet['business']) if entry['response'] is not None
                            for c,other in enumerate(packet['code']) if other['response'] is not None]
    sealed=seal_packet(packet)
    if len(canonical_bytes(sealed))>config.limits.max_bytes: raise ValueError('packet exceeded budget; narrow scope')
    return sealed
