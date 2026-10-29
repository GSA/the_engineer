"""Supported read-only MCP transport for qualified business evidence."""
import asyncio
from contextlib import asynccontextmanager
from dataclasses import asdict
import json
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from .errors import ProviderError
from .packet import canonical_bytes


class LibrarianClient:
    def __init__(self, session, binding, limits, info):
        self.session, self.binding, self.limits, self.info = session, binding, limits, info

    @classmethod
    @asynccontextmanager
    async def open(cls, binding, limits):
        args = ['--root', str(binding.root), '--reader', str(binding.reader),
                '--timeout-seconds', str(limits.timeout_seconds)]
        if binding.selection is not None:
            args += ['--manifest', str(binding.selection)]
        params = StdioServerParameters(command=str(binding.executable), args=args, env=dict(os.environ))
        try:
            # SDK transport owns shutdown; each request has its own timeout.
            with open(os.devnull, 'w') as errlog:
                async with stdio_client(params, errlog=errlog) as (read, write):
                    async with ClientSession(read, write) as session:
                        info = await asyncio.wait_for(session.initialize(), limits.timeout_seconds)
                        if (info.server_info.name, info.server_info.version) != ('the-librarian', '0.3.0'):
                            raise ProviderError('unavailable', 'unsupported Librarian identity')
                        tools = await asyncio.wait_for(session.list_tools(), limits.timeout_seconds)
                        if not {'status', 'get'} <= {tool.name for tool in tools.tools}:
                            raise ProviderError('unavailable', 'missing qualified read tools')
                        yield cls(session, binding, limits, info)
        except ProviderError:
            raise
        except Exception as error:
            # Task-group wrappers may contain source-bearing provider exceptions.
            raise ProviderError('unavailable', 'Librarian transport failed') from None

    async def describe(self):
        binding = {key: str(value) if value is not None else None for key, value in asdict(self.binding).items()}
        return {'identity_kind': 'configured', 'binding': binding,
                'server': {'name': self.info.server_info.name, 'version': self.info.server_info.version}}

    async def _call(self, name, arguments):
        try:
            result = await asyncio.wait_for(self.session.call_tool(name, arguments), self.limits.timeout_seconds)
            if result.is_error or len(result.content) != 1 or result.content[0].type != 'text':
                raise ValueError()
            text = result.content[0].text
            if len(text.encode('utf-8')) > self.limits.max_bytes:
                raise ValueError()
            value = json.loads(text)
            if not isinstance(value, dict): raise ValueError()
            canonical_bytes(value)
            return value
        except Exception:
            raise ProviderError('unavailable', 'Librarian read failed or exceeded budget') from None

    async def status(self):
        result = await self._call('status', {})
        if result.get('fresh') is not True:
            raise ProviderError('stale', 'Librarian selected index is not fresh')
        return result

    async def get(self, locator):
        result = await self._call('get', {'locator': locator, 'format': 'full'})
        pieces = result.get('pieces')
        if not isinstance(pieces, list) or not pieces or 'handling' not in result:
            raise ProviderError('missing', 'qualified business evidence unavailable')
        required = {'locator', 'path', 'source_hash', 'line_start', 'line_end', 'text', 'reasons'}
        if any(not isinstance(piece, dict) or not required <= piece.keys() for piece in pieces):
            raise ProviderError('missing', 'qualified business pieces malformed')
        return result
