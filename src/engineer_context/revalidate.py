"""Point-in-time rechecks do not authorize actions or replace history."""
import copy
from contextlib import AsyncExitStack
from .collect import UnavailableClient, now
from .librarian import LibrarianClient, ProviderError
from .packet import canonical_bytes, canonical_digest, validate_packet


async def revalidate(config, packet, task):
    validate_packet(packet,task)
    async with AsyncExitStack() as stack:
        try:
            business=await stack.enter_async_context(LibrarianClient.open(config.librarian,config.limits))
        except ProviderError as error: business=UnavailableClient(error)
        return await revalidate_with_clients(config,packet,task,business)


async def revalidate_with_clients(config, packet, task, librarian):
    validate_packet(packet,task)
    if len(canonical_bytes(packet))>config.limits.max_bytes: raise ValueError('packet exceeded budget')
    result=dict(schema='engineer.context-revalidation/v1',packet_digest=packet['digest'],task=copy.deepcopy(packet['task']),
                observed_at=now(),checks=[],readiness=packet['readiness'])

    def check(index,required,error=None):
        value=dict(provider='librarian',scope=index,required=required,status='unchanged' if error is None else error.status,
                   reason='point-in-time evidence unchanged' if error is None else error.reason)
        result['checks'].append(value)
        if required and error is not None: result['readiness']='blocked'

    binding_error=None
    try:
        description=await librarian.describe(); status=await librarian.status()
        if status.get('fresh') is not True: raise ProviderError('stale','business context not fresh')
        if canonical_digest(description)!=canonical_digest(packet['providers'].get('librarian',{}).get('description')):
            raise ProviderError('changed','business binding changed')
    except ProviderError as error: binding_error=error

    for index,entry in enumerate(packet['business']):
        try:
            if binding_error: raise binding_error
            if entry['response'] is None: raise ProviderError('missing','historical evidence missing')
            observed=await librarian.get(entry['request']['locator'])
            if canonical_digest(observed)!=canonical_digest(entry['response']):
                raise ProviderError('changed','qualified evidence or immutable identity changed')
            check(index,entry['required'])
        except ProviderError as error: check(index,entry['required'],error)
    if len(canonical_bytes(result))>config.limits.max_bytes: raise ValueError('revalidation exceeded budget')
    return result
