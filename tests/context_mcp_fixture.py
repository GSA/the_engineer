"""Failure-injection transport fixture, not owning-provider acceptance."""
import asyncio
import json
import os
from pathlib import Path
from mcp.server import MCPServer
from mcp.types import TextContent

mode = os.environ.get('CONTEXT_TEST_MODE', 'normal')
if os.environ.get('CONTEXT_TEST_PID'):
    Path(os.environ['CONTEXT_TEST_PID']).write_text(str(os.getpid()))
server = MCPServer('wrong' if mode == 'wrong' else 'the-librarian', version='0.3.0')

@server.tool(structured_output=False)
async def status() -> TextContent:
    if mode == 'hang': await asyncio.sleep(60)
    return TextContent(type='text', text=json.dumps({'fresh': mode != 'stale'}))

if mode != 'missing':
    @server.tool(structured_output=False)
    async def get(locator: str, format: str = 'full') -> TextContent:
        if mode == 'error': raise ValueError('injected secret error')
        response = {'handling': ['private'], 'pieces': [{'locator': locator, 'path': 'doc.md',
                    'source_hash': 'abc', 'line_start': 1, 'line_end': 1,
                    'text': 'x' * 5000 if mode == 'large' else 'Exact passage', 'reasons': ['qualified']}]}
        return TextContent(type='text', text=json.dumps(response))

if __name__ == '__main__': server.run()
