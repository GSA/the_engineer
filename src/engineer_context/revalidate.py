"""Point-in-time rechecks do not authorize actions or replace history."""
import asyncio
import copy
from contextlib import AsyncExitStack
from .collect import UnavailableClient, incomplete_code, now, pin_selector
from .knowitall import KnowitallClient
from .librarian import LibrarianClient, ProviderError
from .packet import canonical_bytes, canonical_digest, validate_packet


async def revalidate(config, packet, task):
    validate_packet(packet,task)
    async with AsyncExitStack() as stack:
        try:
            business=await stack.enter_async_context(LibrarianClient.open(config.librarian,config.limits))
        except ProviderError as error: business=UnavailableClient(error)
        return await revalidate_with_clients(config,packet,task,business,KnowitallClient(config.knowitall,config.limits))


async def revalidate_with_clients(config, packet, task, librarian, knowitall):
    validate_packet(packet,task)
    if len(canonical_bytes(packet))>config.limits.max_bytes: raise ValueError('packet exceeded budget')
    result=dict(schema='engineer.context-revalidation/v1',packet_digest=packet['digest'],task=copy.deepcopy(packet['task']),
                observed_at=now(),checks=[],readiness=packet['readiness'])

    def check(provider,index,required,error=None):
        value=dict(provider=provider,scope=index,required=required,status='unchanged' if error is None else error.status,
                   reason='point-in-time evidence unchanged' if error is None else error.reason)
        result['checks'].append(value)
        if required and error is not None: result['readiness']='blocked'

    errors={}
    try:
        description=await librarian.describe(); status=await librarian.status()
        if status.get('fresh') is not True: raise ProviderError('stale','business context not fresh')
        if canonical_digest(description)!=canonical_digest(packet['providers'].get('librarian',{}).get('description')):
            raise ProviderError('changed','business binding changed')
    except ProviderError as error: errors['librarian']=error
    try:
        description=await asyncio.to_thread(knowitall.describe)
        if canonical_digest(description)!=canonical_digest(packet['providers'].get('knowitall',{}).get('description')):
            raise ProviderError('changed','code binding changed')
    except ProviderError as error: errors['knowitall']=error

    for provider,key in [('librarian','business'),('knowitall','code')]:
        for index,entry in enumerate(packet[key]):
            try:
                if provider in errors: raise errors[provider]
                if entry['response'] is None: raise ProviderError('missing','historical evidence missing')
                if key=='business':
                    observed=await librarian.get(entry['request']['locator'])
                else:
                    query=copy.deepcopy(entry['request'])
                    resolved=entry['response'].get('resolved')
                    if resolved is None: raise ProviderError('missing','historical code identity missing')
                    if 'continuation' in query:
                        # The owning provider binds a page token to the whole selector, so
                        # repinning it here would invalidate an otherwise valid page.
                        # Currency is checked separately against the same generation.
                        probe=copy.deepcopy(query); probe.pop('continuation'); probe['selector']=pin_selector(resolved)
                        current=await asyncio.to_thread(knowitall.query,probe)
                        if current.get('status')=='stale' or canonical_digest(current.get('resolved'))!=canonical_digest(resolved):
                            raise ProviderError('stale','pinned code generation is no longer current')
                    else:
                        query['selector']=pin_selector(resolved)
                    observed=await asyncio.to_thread(knowitall.query,query)
                    for field in ('contract','request_id','project_id','repository_id'):
                        if observed.get(field)!=query.get(field): raise ProviderError('invalid','code response identity mismatch')
                    if incomplete_code(observed): raise ProviderError('partial','required code scope incomplete')
                if canonical_digest(observed)!=canonical_digest(entry['response']):
                    raise ProviderError('changed','qualified evidence or immutable identity changed')
                check(provider,index,entry['required'])
            except ProviderError as error: check(provider,index,entry['required'],error)
    if len(canonical_bytes(result))>config.limits.max_bytes: raise ValueError('revalidation exceeded budget')
    return result
