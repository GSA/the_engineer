"""Failure-injection transport fixture, not owning-provider acceptance."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
from mcp.server import MCPServer
from mcp.types import TextContent

mode = os.environ.get('CONTEXT_TEST_MODE', 'normal')
# Mirror the owning launch contracts: the current toolkit loads its reader
# module from --root, and only a legacy release accepts --reader.
parser = argparse.ArgumentParser()
parser.add_argument('--root', required=True)
parser.add_argument('--manifest')
parser.add_argument('--timeout-seconds', type=float)
if mode == 'legacy': parser.add_argument('--reader', required=True)
parser.parse_args(sys.argv[1:])
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
