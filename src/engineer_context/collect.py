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


# Minimal shape of the owning request contract, so an incomplete query is a
# caller error here instead of a provider round trip, even when the selected
# provider is unreachable. The owning validator in the bridge stays
# authoritative; this mirrors its request schema only.
CODE_FIELDS = (['contract','request_id','project_id','repository_id','selector','query'],['continuation'])
CODE_SELECTORS = {'exact':['mode','snapshot_id','generation_id','freshness'],'current':['mode']}
CODE_QUERIES = {'symbol':['kind','name','match'],'dependencies':['kind','symbol_id','direction','relationship_kinds'],
                'path':['kind','path'],'source_range':['kind','path','start','end']}


def code_path(value):
    parts=value.split('/') if isinstance(value,str) else []
    if not parts or any(part in ('','.','..') for part in parts): raise ValueError('invalid code path')


def code_position(value):
    exact_fields(value,['line','column'])
    for field in ['line','column']:
        if type(value[field]) is not int or value[field]<1: raise ValueError('invalid source position')


def code_scope(scope):
    if not isinstance(scope,dict) or scope.get('kind') not in CODE_QUERIES: raise ValueError('invalid code query')
    exact_fields(scope,CODE_QUERIES[scope['kind']])
    kind=scope['kind']
    if kind=='symbol':
        identity(scope['name'])
        if scope['match'] not in ('exact','normalized'): raise ValueError('invalid symbol match')
    elif kind=='dependencies':
        identity(scope['symbol_id'])
        if scope['direction'] not in ('incoming','outgoing'): raise ValueError('invalid dependency direction')
        kinds=scope['relationship_kinds']
        if not isinstance(kinds,list) or not kinds or len(set(kinds))!=len(kinds): raise ValueError('invalid relationship kinds')
        for value in kinds: identity(value)
    else:
        code_path(scope['path'])
        if kind=='source_range':
            for field in ['start','end']: code_position(scope[field])


def validate_code_request(config, query):
    if not isinstance(query,dict): raise ValueError('invalid code request')
    exact_fields(query,*CODE_FIELDS)
    if query['contract']!='knowitall.code-context/v1': raise ValueError('unexpected code contract')
    identity(query['request_id'])
    if query['project_id']!=config.knowitall.project_id or query['repository_id']!=config.knowitall.repository_id:
        raise ValueError('code binding mismatch')
    if 'continuation' in query: identity(query['continuation'])
    selector=query['selector']
    if not isinstance(selector,dict) or selector.get('mode') not in CODE_SELECTORS:
        raise ValueError('invalid code selector')
    exact_fields(selector,CODE_SELECTORS[selector['mode']])
    if selector['mode']=='exact':
        for field in ['snapshot_id','generation_id']: identity(selector[field])
        if selector['freshness'] not in ('allow_historical','require_current'): raise ValueError('invalid code freshness')
    code_scope(query['query'])


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
            else: validate_code_request(config,item['request'])


def page_scope(response):
    """Incompleteness other than pagination, which a packet's chain covers."""
    return (response.get('status')!='ok' or bool(response.get('ambiguities'))
            or bool(response.get('missing_evidence'))
            or response.get('coverage',{}).get('relevant_scope')!='complete')


def pin_selector(resolved):
    return dict(mode='exact', snapshot_id=resolved['snapshot_id'], generation_id=resolved['generation_id'], freshness='require_current')


def page_shape(query):
    """Identify the paged query: a page differs only by token and request id."""
    return canonical_bytes({k:v for k,v in query.items() if k not in ('continuation','request_id')})


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
    pinned=None; pages={}
    for index,item in enumerate(request['code']):
        query=item['request']
        held=query.get('continuation')
        # A held page token is bound to the selector that issued it, so it is
        # replayed unchanged and its identity is compared after the response.
        if query['selector']['mode']=='current' and pinned is not None and held is None:
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
            if held is not None and resolved is not None and pinned is not None:
                if any(resolved.get(field)!=pinned.get(field) for field in ('snapshot_id','generation_id')):
                    raise ProviderError('stale','continuation page left the pinned code generation')
            if query['selector']['mode']=='current' and resolved is not None and pinned is None: pinned=copy.deepcopy(resolved)
            entry['response']=response
            pages[index]=dict(held=held,issued=response.get('continuation'),resolved=resolved,shape=page_shape(query))
        except ProviderError as error: issue('knowitall',index,item['required'],error)
        packet['code'].append(entry)
    # A single page is partial evidence: the whole requested scope is only
    # present when this packet also holds the pages before and after it.
    issuer={page['issued']:index for index,page in pages.items() if page['issued'] is not None}
    consumer={page['held']:index for index,page in pages.items() if page['held'] is not None}

    def walk(index, key, neighbours):
        """Follow one page direction while tokens remain, same query and generation."""
        seen=set()
        while True:
            page=pages[index]; token=page[key]
            if token is None: return True
            other=neighbours.get(token)
            if other is None or other in seen: return False
            if pages[other]['shape']!=page['shape'] or pages[other]['resolved']!=page['resolved']: return False
            seen.add(index); index=other

    for index,page in pages.items():
        required=packet['code'][index]['required']
        if not (walk(index,'held',issuer) and walk(index,'issued',consumer)):
            issue('knowitall',index,required,ProviderError('partial','other pages of this code query are absent'))
        elif page_scope(packet['code'][index]['response']):
            issue('knowitall',index,required,ProviderError('partial','code scope incomplete'))
    packet['associations']=[dict(business=b,code=c,status='unasserted')
                            for b,entry in enumerate(packet['business']) if entry['response'] is not None
                            for c,other in enumerate(packet['code']) if other['response'] is not None]
    sealed=seal_packet(packet)
    if len(canonical_bytes(sealed))>config.limits.max_bytes: raise ValueError('packet exceeded budget; narrow scope')
    return sealed
