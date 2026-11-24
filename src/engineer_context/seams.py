"""Redistributable, zero-dependency cross-repository seam & orphan-handler scanner.

Scoped strictly to cross-repository and cross-layer architectural boundaries
(UI HTTP -> API Gateway -> CDK Stack -> Lambda Handler, orphan/stub handler
audits, SQS event-source wiring, and CloudFormation cross-stack imports).
The scanner is content-driven and project-agnostic: every seam and every
`detail` string is derived from text matched in the scanned files, and heuristic
findings are worded as possible mismatches. Intentionally avoids
intra-repository AST/PageRank indexing so output remains compact (<2-4 KB) and
grounded in exact file:line citations.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys

SCHEMA = 'engineer.cross-repo-seams/v1'
SKIP_DIRS = {'.git', 'node_modules', 'dist', 'build', 'cdk.out', '.venv', 'venv', '__pycache__', 'coverage', '.angular'}
SEAM_KINDS = (
    'ui_to_apigw_route',
    'apigw_to_lambda',
    'cdk_wires_lambda',
    'orphan_lambda_directory',
    'async_event_flow',
    'cfn_cross_stack_import',
    'canary_and_pattern_config',
)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return ''


def _find_line_optional(path: Path, pattern: str) -> int | None:
    text = _read_text(path)
    if not text:
        return None
    rx = re.compile(pattern)
    for idx, line in enumerate(text.splitlines(), start=1):
        if rx.search(line):
            return idx
    return None


def _find_line(path: Path, pattern: str, default: int = 1) -> int:
    found = _find_line_optional(path, pattern)
    return found if found is not None else default


def _iter_source_files(root: Path, suffixes: tuple[str, ...] = ('.ts', '.js', '.py', '.json')):
    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        base = Path(dirpath)
        dirnames[:] = sorted(
            d for d in dirnames
            if d not in SKIP_DIRS and not d.startswith('.') and not (base / d).is_symlink()
        )
        for name in sorted(filenames):
            if name.endswith(('.spec.ts', '.test.ts', '.spec.js', '.test.js', '.d.ts')):
                continue
            path = base / name
            if path.suffix in suffixes and path.is_file() and not path.is_symlink():
                yield path


def resolve_repositories(repos: list[str | Path] | None = None, workspace_root: str | Path | None = None) -> dict[str, Path]:
    """Resolve explicit repository paths or discover repositories under workspace_root."""
    resolved: dict[str, Path] = {}
    if workspace_root is not None:
        base = Path(workspace_root).expanduser().resolve()
        if not base.is_dir():
            raise ValueError(f'workspace root is not a directory: {base}')
        for child in sorted(base.iterdir()):
            if child.is_dir() and not child.name.startswith('.'):
                resolved[child.name] = child.resolve()
    for raw in repos or ():
        path = Path(raw).expanduser().resolve()
        if not path.is_dir():
            raise ValueError(f'repository path is not a directory: {path}')
        resolved[path.name] = path
    if not resolved:
        raise ValueError('at least one repository path or --workspace-root is required')
    return resolved


def _classify_handler_health(entry_path: Path) -> str | None:
    """Detect pre-AI stub, commented-out, or deprecated no-op Lambda handlers."""
    text = _read_text(entry_path)
    if not text:
        return None
    lower = text.lower()
    if 'not in use' in lower or 'no longer in use' in lower or 'deprecated' in lower:
        return f'DEPRECATED MARKER: {entry_path.name} contains a "not in use" or "deprecated" marker.'
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    commented = [ln for ln in lines if ln.startswith('//') or ln.startswith('/*') or ln.startswith('*')]
    if len(commented) >= 8 and ('await ' in '\n'.join(commented) or 'try {' in '\n'.join(commented)):
        active_code = '\n'.join(ln for ln in lines if not (ln.startswith('//') or ln.startswith('/*') or ln.startswith('*')))
        if 'await ' not in active_code:
            return f'COMMENTED-OUT BODY: {entry_path.name} has 8+ comment lines containing code and no active `await`.'
    return None


def _discover_handlers(repo_map: dict[str, Path]) -> list[dict]:
    """Find Lambda handler directories across `assets/lambda/*` and `functions/*`."""
    handlers: list[dict] = []
    for repo_name, root in sorted(repo_map.items()):
        for rel_parent, sub_candidates in [
            ('assets/lambda', ('index.ts', 'index.js', 'index.py', 'handler.ts', 'handler.py')),
            ('functions', ('src/index.ts', 'src/index.js', 'src/index.py', 'index.ts', 'index.py')),
        ]:
            parent = root / rel_parent
            if not parent.is_dir():
                continue
            for child in sorted(parent.iterdir()):
                if not child.is_dir() or child.name.startswith('.'):
                    continue
                entry_rel = None
                for cand in sub_candidates:
                    if (child / cand).is_file():
                        entry_rel = f'{rel_parent}/{child.name}/{cand}'
                        break
                if entry_rel is None:
                    entry_rel = f'{rel_parent}/{child.name}'
                entry_abs = root / entry_rel
                stub_note = _classify_handler_health(entry_abs) if entry_abs.is_file() else None
                returns_batch_failures = False
                for src_file in _iter_source_files(child, ('.ts', '.js', '.py')):
                    if 'batchItemFailures' in _read_text(src_file):
                        returns_batch_failures = True
                        break
                handlers.append({
                    'repo': repo_name,
                    'root': root,
                    'name': child.name,
                    'dir_rel': f'{rel_parent}/{child.name}',
                    'entry_rel': entry_rel,
                    'stub_note': stub_note,
                    'returns_batch_failures': returns_batch_failures,
                })
    return handlers


def _resource_paths(c_text: str) -> dict[str, str]:
    """Map CDK resource variables to full paths, following chained and parent-variable addResource calls."""
    paths: dict[str, str] = {}
    for m in re.finditer(r'(?:const|let|var|this\.)\s*(\w+)\s*=\s*((?:(?!\n\s*(?:const|let|var|this\.)\b)[^;])+)', c_text):
        rhs = m.group(2)
        segs = re.findall(r'\.addResource\(\s*["\']([^"\']+)["\']\s*\)', rhs)
        if not segs:
            continue
        base = rhs.split('.addResource(', 1)[0].strip().split('.')[-1]
        parent = paths.get(base, '')
        paths[m.group(1)] = '/'.join(p for p in [parent.strip('/'), *(x.strip('/') for x in segs)] if p)
    return paths


def _receiver_path(receiver: str, paths: dict[str, str]) -> str | None:
    segs = re.findall(r'\.addResource\(\s*["\']([^"\']+)["\']\s*\)', receiver)
    if segs:
        base = receiver.split('.addResource(', 1)[0].strip().split('.')[-1]
        return '/'.join(p for p in [paths.get(base, '').strip('/'), *(x.strip('/') for x in segs)] if p)
    return paths.get(receiver.split('.')[-1])


def _route_segments(path: str) -> list[str]:
    cleaned = re.sub(r'\$\{[^}]+\}', '{}', path)
    return ['{}' if (x.startswith('{') or x.startswith(':')) else x for x in cleaned.strip('/').split('/') if x]


def _routes_match(ui_path: str, api_path: str) -> bool:
    """Whole-segment match; the UI path may carry an API base prefix before the API route."""
    ui, api = _route_segments(ui_path), _route_segments(api_path)
    if not api or len(ui) < len(api):
        return False
    return all(a == b or '{}' in (a, b) for a, b in zip(ui[-len(api):], api))


def _discover_cdk_files(repo_map: dict[str, Path]) -> list[tuple[str, Path, str, str]]:
    """Return (repo_name, abs_path, rel_path, text) for CDK/infrastructure files."""
    cdk_files: list[tuple[str, Path, str, str]] = []
    for repo_name, root in sorted(repo_map.items()):
        for path in _iter_source_files(root, ('.ts', '.py')):
            rel = path.relative_to(root).as_posix()
            if any(seg in rel for seg in ('lib/', 'infrastructure/', 'cdk/', 'bin/')):
                text = _read_text(path)
                if any(tok in text for tok in (
                    'aws-cdk', 'cdk-patterns', 'NodejsFunction', 'NodejsVersioned',
                    'addResource', 'addMethod', 'SqsEventSource', 'KinesisEventSource',
                    'Fn.importValue', 'StringParameter', 'CfnOutput', 'functions/', 'assets/lambda'
                )) or rel.endswith('constants.ts'):
                    cdk_files.append((repo_name, path, rel, text))
    return cdk_files


def scan_seams(repo_map: dict[str, Path]) -> list[dict]:
    """Scan supplied repositories for cross-repository and cross-layer seams."""
    seams: list[dict] = []
    seq = 0

    def add_seam(
        kind: str,
        s_repo: str,
        s_path: str,
        s_line: int,
        s_sym: str,
        t_repo: str,
        t_path: str,
        t_line: int,
        t_sym: str,
        resource: str,
        detail: str,
    ):
        nonlocal seq
        seq += 1
        seams.append({
            'seam_id': f'seam-{seq:04d}',
            'seam_kind': kind,
            'source_repo': s_repo,
            'source_path': s_path,
            'source_line': s_line,
            'source_symbol': s_sym,
            'target_repo': t_repo,
            'target_path': t_path,
            'target_line': t_line,
            'target_symbol': t_sym,
            'route_or_resource': resource,
            'detail': detail,
        })

    handlers = _discover_handlers(repo_map)
    cdk_files = _discover_cdk_files(repo_map)

    # 1. CDK -> Lambda handler wiring & orphan handler detection across all repos
    for h in handlers:
        h_name = h['name']
        exact_pat = rf"['\"/`]{re.escape(h_name)}['\"/`]"
        matches: list[tuple[str, Path, str, int, str]] = []
        for c_repo, c_path, c_rel, c_text in cdk_files:
            if re.search(exact_pat, c_text):
                line_no = _find_line(c_path, exact_pat)
                lines = c_text.splitlines()
                window = '\n'.join(lines[max(0, line_no - 15):min(len(lines), line_no + 5)])
                props = re.findall(r'this\.([a-zA-Z0-9_]+)\s*=', window)
                sym = f"Functions.{props[-1]}" if props else f"CDK:{Path(c_rel).stem}:{h_name}"
                matches.append((c_repo, c_path, c_rel, line_no, sym))

        if matches:
            # Prefer non-apigateway construct file first (e.g. lib/functions.ts or models/constants.ts)
            matches.sort(key=lambda item: (1 if 'apigateway' in item[2] else 0, item[0] != h['repo'], item[2]))
            c_repo, c_path, c_rel, line_no, sym = matches[0]
            notes = [f"CDK {c_repo}:{c_rel} wires {h['repo']}:{h['entry_rel']}"]
            if h['stub_note']:
                notes.append(h['stub_note'])
            add_seam(
                'cdk_wires_lambda',
                c_repo,
                c_rel,
                line_no,
                sym,
                h['repo'],
                h['entry_rel'],
                1,
                f"{h_name}.handler",
                f"lambda:{h_name}",
                ' | '.join(notes),
            )
        else:
            default_cdk = 'lib/functions.ts' if (h['root'] / 'lib/functions.ts').is_file() else 'CDK'
            orphan_notes = [
                f"{h['dir_rel']} exists in {h['repo']} but its name was not found in any scanned CDK/infrastructure file."
            ]
            if h['stub_note']:
                orphan_notes.append(h['stub_note'])
            add_seam(
                'orphan_lambda_directory',
                h['repo'],
                h['entry_rel'],
                1,
                f"{h_name}.handler [STUB]" if h['stub_note'] else f"{h_name}.handler",
                h['repo'],
                default_cdk,
                1,
                'UNWIRED_IN_CDK',
                f"orphan:{h_name}",
                ' | '.join(orphan_notes),
            )

    seen_route_keys: set[tuple[str, str, str]] = set()
    seen_apigw_keys: set[tuple[str, str, str]] = set()
    seen_async_keys: set[tuple[str, str, str]] = set()

    # 2. Content-driven UI -> API Gateway, API Gateway -> Lambda, Async SQS, and CloudFormation seams across ANY repositories
    generic_apigw_routes: list[dict] = []
    for c_repo, c_path, c_rel, c_text in cdk_files:
        resource_paths = _resource_paths(c_text)
        for match in re.finditer(
            r'([\w.]*(?:\([^()]*\)[\w.]*)*)\.addMethod\(\s*["\'](GET|POST|PUT|DELETE|PATCH)["\']([^\n;]*)',
            c_text,
        ):
            res_expr, verb, rest = match.group(1), match.group(2), match.group(3)
            line_no = c_text[:match.start()].count('\n') + 1
            res_seg = _receiver_path(res_expr, resource_paths) or res_expr.split('.')[-1]
            route_str = f"{verb} /{res_seg.strip('/')}"
            generic_apigw_routes.append({
                'repo': c_repo,
                'path': c_rel,
                'line': line_no,
                'verb': verb,
                'route': route_str,
                'segment': res_seg.strip('/'),
                'rest': rest,
                'text': c_text,
            })
            # Match to a discovered handler if referenced on the addMethod line or in the same CDK file
            for h in handlers:
                h_token = h['name']
                h_camel = re.sub(r'-([a-z])', lambda m: m.group(1).upper(), h_token)
                if h_token in rest or h_camel in rest or (h_token in c_text and len(handlers) == 1):
                    key = (c_repo, c_rel, route_str)
                    if key in seen_apigw_keys:
                        continue
                    seen_apigw_keys.add(key)
                    lam_abs = h['root'] / h['entry_rel']
                    lam_text = _read_text(lam_abs)
                    sym = f"{h['name']}.handler"
                    detail = f"API Gateway {route_str} in {c_repo}:{c_rel} invokes {h['repo']}:{h['entry_rel']}."
                    if (
                        re.search(r'httpMethod', lam_text)
                        and not re.search(rf"""['"]{verb}['"]""", lam_text)
                    ):
                        sym = f"{sym} [ROUTE_MISMATCH]"
                        detail = (
                            f"POSSIBLE MISMATCH: {c_repo}:{c_rel}:L{line_no} wires {route_str} to "
                            f"{h['repo']}:{h['entry_rel']}, which mentions httpMethod "
                            f"but contains no quoted '{verb}' string."
                        )
                    add_seam(
                        'apigw_to_lambda',
                        c_repo,
                        c_rel,
                        line_no,
                        f"{Path(c_rel).stem}:{route_str}",
                        h['repo'],
                        h['entry_rel'],
                        _find_line(lam_abs, r'export|handler|httpMethod'),
                        sym,
                        route_str,
                        detail,
                    )

        # Generic SqsEventSource -> handler batch failure check
        for sqs_match in re.finditer(r'(?:(\w+)\s*\.addEventSource\(\s*)?new\s+[a-zA-Z0-9_.]*SqsEventSource\(([^)]*)\)', c_text):
            sqs_args = sqs_match.group(2)
            line_no = c_text[:sqs_match.start()].count('\n') + 1
            reports_failures = bool(re.search(r'reportBatchItemFailures\s*:\s*true', sqs_args))
            repo_handlers = [x for x in handlers if x['repo'] == c_repo]
            receiver = sqs_match.group(1)
            if receiver:
                decl = re.search(rf'\b{re.escape(receiver)}\s*=\s*([^;]*)', c_text)
                scoped = [x for x in repo_handlers if decl and x['name'] in decl.group(1)]
                repo_handlers = scoped or repo_handlers
            for h in repo_handlers:
                if h['name'] in c_text or len(repo_handlers) == 1:
                    key = (c_repo, c_rel, h['entry_rel'])
                    if key in seen_async_keys:
                        continue
                    seen_async_keys.add(key)
                    mismatch = h['returns_batch_failures'] and not reports_failures
                    add_seam(
                        'async_event_flow',
                        c_repo,
                        c_rel,
                        line_no,
                        f"{Path(c_rel).stem}:SqsEventSource",
                        h['repo'],
                        h['entry_rel'],
                        1,
                        f"{h['name']}.handler [BATCH_FAILURE_MISMATCH]" if mismatch else f"{h['name']}.handler",
                        f"SQS -> {h['name']}",
                        (
                            f"POSSIBLE MISMATCH: {h['repo']}:{h['entry_rel']} mentions batchItemFailures, "
                            f"but the SqsEventSource at {c_repo}:{c_rel}:L{line_no} has no reportBatchItemFailures: true in its arguments."
                            if mismatch
                            else f"{c_repo}:{c_rel}:L{line_no} SqsEventSource triggers {h['repo']}:{h['entry_rel']}."
                        ),
                    )

    # Generic UI HTTP calls -> discovered API Gateway routes across any repository names
    for repo_name, root in sorted(repo_map.items()):
        for path in _iter_source_files(root, ('.ts', '.js')):
            rel = path.relative_to(root).as_posix()
            if not any(tok in rel.lower() for tok in ('service', 'client', 'api')):
                continue
            text = _read_text(path)
            for http_match in re.finditer(
                r'\bhttp\.(get|post|put|delete|patch)\b[^\n;]*?["\'`](/[a-zA-Z0-9_{}/-]+)["\'`]',
                text,
            ):
                verb = http_match.group(1).upper()
                url_path = http_match.group(2)
                ui_line = text[:http_match.start()].count('\n') + 1
                for gw in generic_apigw_routes:
                    if gw['verb'] == verb and gw['segment'] and _routes_match(url_path, gw['segment']):
                        key = (repo_name, rel, gw['route'])
                        if key in seen_route_keys:
                            continue
                        seen_route_keys.add(key)
                        add_seam(
                            'ui_to_apigw_route',
                            repo_name,
                            rel,
                            ui_line,
                            f"{Path(rel).stem}:{verb} {url_path}",
                            gw['repo'],
                            gw['path'],
                            gw['line'],
                            f"{Path(gw['path']).stem}:{gw['route']}",
                            gw['route'],
                            f"UI HTTP {verb} {url_path} in {repo_name}:{rel} -> API Gateway {gw['route']} in {gw['repo']}:{gw['path']}",
                        )

    # 3. Generic CloudFormation Fn.importValue & Canary Pattern Seams across any supplied repos
    for c_repo, c_path, c_rel, c_text in cdk_files:
        if 'Fn.importValue' in c_text:
            line_no = _find_line(c_path, r'Fn\.importValue')
            add_seam(
                'cfn_cross_stack_import',
                c_repo,
                c_rel,
                line_no,
                f'{Path(c_rel).stem}.importValue',
                c_repo,
                c_rel,
                line_no,
                'CloudFormationExport',
                'Fn.importValue',
                f'{c_repo}:{c_rel}:L{line_no} imports cross-stack CloudFormation export via Fn.importValue.',
            )
        if 'trafficShifting' in c_text or ('blueGreen' in c_text and 'cdk-patterns' in c_text):
            line_no = _find_line(c_path, r'trafficShifting|blueGreen')
            add_seam(
                'canary_and_pattern_config',
                c_repo,
                c_rel,
                line_no,
                f'{Path(c_rel).stem}.canaryConfig',
                c_repo,
                c_rel,
                line_no,
                'trafficShifting',
                'canary:blueGreen',
                f'{c_repo}:{c_rel}:L{line_no} contains a trafficShifting or blueGreen deployment setting.',
            )

    return seams


def filter_seams(seams: list[dict], query: str = '', kind: str = '') -> list[dict]:
    """Filter seams by case-insensitive substring query and/or seam_kind."""
    q = query.strip().lower()
    k = kind.strip().lower()
    results = []
    for s in seams:
        if k and s['seam_kind'].lower() != k:
            continue
        if q:
            haystack = ' '.join(
                str(s.get(field, ''))
                for field in (
                    'seam_kind', 'source_repo', 'source_path', 'source_symbol',
                    'target_repo', 'target_path', 'target_symbol', 'route_or_resource', 'detail'
                )
            ).lower()
            if q not in haystack:
                continue
        results.append(s)
    return results


def render_seams(repo_map: dict[str, Path], seams: list[dict], fmt: str = 'compact', max_chars: int = 4000) -> str:
    """Render filtered seams in compact 1-line text, Markdown table, or JSON."""
    if max_chars <= 0:
        raise ValueError('max_chars must be positive')
    if fmt not in ('compact', 'markdown', 'json'):
        raise ValueError('format must be compact, markdown, or json')

    by_kind: dict[str, int] = {}
    for s in seams:
        by_kind[s['seam_kind']] = by_kind.get(s['seam_kind'], 0) + 1

    if fmt == 'json':
        payload = {
            'schema': SCHEMA,
            'repositories': sorted(repo_map.keys()),
            'total_seams': len(seams),
            'counts_by_kind': by_kind,
            'seams': seams,
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        if len(raw) <= max_chars:
            return raw
        # Trim seams list to fit max_chars while preserving valid JSON
        kept = list(seams)
        while kept and len(raw) > max_chars:
            kept.pop()
            payload['seams'] = kept
            payload['truncated'] = True
            raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        if len(raw) > max_chars:
            raise ValueError(
                f'max_chars ({max_chars}) is too small for the minimum JSON seam envelope ({len(raw)} chars)'
            )
        return raw

    if fmt == 'markdown':
        lines = [
            f'# Cross-Repository Seam Map ({len(seams)} seams across {len(repo_map)} repos)',
            '',
            '| Seam Kind | Source (`repo:path:line`) | Route / Resource | Target (`repo:path:line`) | Detail |',
            '| --- | --- | --- | --- | --- |',
        ]
        for s in seams:
            src = f"`{s['source_repo']}:{s['source_path']}:L{s['source_line']}` ({s['source_symbol']})"
            tgt = f"`{s['target_repo']}:{s['target_path']}:L{s['target_line']}` ({s['target_symbol']})"
            lines.append(f"| `{s['seam_kind']}` | {src} | `{s['route_or_resource']}` | {tgt} | {s['detail']} |")
    else:
        summary = ', '.join(f'{k}={v}' for k, v in sorted(by_kind.items())) or 'none'
        lines = [f'# Cross-Repo Seams: {len(seams)} matched ({summary}) across {sorted(repo_map.keys())}']
        for s in seams:
            lines.append(
                f"[{s['seam_kind']}] {s['source_repo']}:{s['source_path']}:L{s['source_line']} ({s['source_symbol']}) "
                f"--[{s['route_or_resource']}]--> "
                f"{s['target_repo']}:{s['target_path']}:L{s['target_line']} ({s['target_symbol']}) | {s['detail']}"
            )

    footer = f'... [truncated to {max_chars} chars; narrow --query or --kind]'
    output_lines: list[str] = []
    used = 0
    for idx, line in enumerate(lines):
        addition = len(line) + (1 if output_lines else 0)
        needs_footer = idx < len(lines) - 1
        reserve = (len(footer) + 1) if needs_footer else 0
        if used + addition + reserve > max_chars and output_lines:
            if used + len(footer) + 1 <= max_chars:
                output_lines.append(footer)
            break
        output_lines.append(line)
        used += addition
    return '\n'.join(output_lines)[:max_chars]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repos', nargs='*', default=[], help='Explicit repository root directories to scan')
    parser.add_argument('--workspace-root', type=Path, default=None, help='Parent directory containing multiple repositories')
    parser.add_argument('--query', default='', help='Case-insensitive substring filter across repos, routes, symbols, or paths')
    parser.add_argument('--kind', default='', choices=['', *SEAM_KINDS], help='Filter to a specific seam kind')
    parser.add_argument('--format', default='compact', choices=['compact', 'markdown', 'json'], help='Output format (default: compact)')
    parser.add_argument('--max-chars', type=int, default=4000, help='Maximum output characters (default: 4000)')
    args = parser.parse_args(argv)
    try:
        repo_map = resolve_repositories(args.repos, args.workspace_root)
        all_seams = scan_seams(repo_map)
        matched = filter_seams(all_seams, query=args.query, kind=args.kind)
        print(render_seams(repo_map, matched, fmt=args.format, max_chars=args.max_chars))
        return 0
    except (ValueError, OSError) as exc:
        print(f'Invalid seam scan input: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
