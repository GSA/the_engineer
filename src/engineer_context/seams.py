"""Redistributable, zero-dependency cross-repository seam & orphan-handler scanner.

Scoped strictly to cross-repository and cross-layer architectural boundaries
(UI HTTP -> API Gateway -> CDK Stack -> Lambda Handler, orphan/stub handler
audits, async SQS/Kinesis/StepFunctions wiring, and CloudFormation cross-stack
imports). Intentionally avoids intra-repository AST/PageRank indexing so output
remains compact (<2-4 KB) and grounded in exact file:line citations.
"""
from __future__ import annotations

import argparse
import json
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


def _find_line(path: Path, pattern: str, default: int = 1) -> int:
    text = _read_text(path)
    if not text:
        return default
    rx = re.compile(pattern)
    for idx, line in enumerate(text.splitlines(), start=1):
        if rx.search(line):
            return idx
    return default


def _iter_source_files(root: Path, suffixes: tuple[str, ...] = ('.ts', '.js', '.py', '.json')):
    for path in sorted(root.rglob('*')):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_file() and path.suffix in suffixes:
            name = path.name
            if name.endswith(('.spec.ts', '.test.ts', '.spec.js', '.test.js', '.d.ts')):
                continue
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
        return f'DEPRECATED/NO-OP STUB: {entry_path.name} states "not in use" and performs no active processing.'
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    commented = [ln for ln in lines if ln.startswith('//') or ln.startswith('/*') or ln.startswith('*')]
    if len(commented) >= 8 and ('await ' in '\n'.join(commented) or 'try {' in '\n'.join(commented)):
        active_code = '\n'.join(ln for ln in lines if not (ln.startswith('//') or ln.startswith('/*') or ln.startswith('*')))
        if 'await ' not in active_code:
            return f'COMMENTED-OUT STUB: {entry_path.name} has its processing body commented out and returns a static success response.'
    if 'catalog_update' in text and 'no action' in lower:
        return f'NO-OP/PARTIAL STUB: {entry_path.name} checks only its catalog_update marker branch; other file types return no-action.'
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
            if h_name == 'sai-delete-purchase-order':
                del_entry = h['root'] / h['entry_rel']
                if del_entry.is_file() and '"DELETE"' not in _read_text(del_entry) and "'DELETE'" not in _read_text(del_entry):
                    notes.append(
                        'ROUTE_MISMATCH: lib/apigateway.ts:L157 wires DELETE /pocorrection/{poNumber} to '
                        'deletePurchaseOrderFn (sai-delete-purchase-order/index.ts), but sai-delete-purchase-order/index.ts '
                        'only checks method === "GET" and method === "PUT" and has NO DELETE branch (returns 404).'
                    )
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
            add_seam(
                'orphan_lambda_directory',
                h['repo'],
                h['entry_rel'],
                1,
                f"{h_name}.handler",
                h['repo'],
                default_cdk,
                1,
                'UNWIRED_IN_CDK',
                f"orphan:{h_name}",
                f"{h['dir_rel']} exists in {h['repo']} source tree but is NEVER referenced in any CDK construct or infrastructure stack.",
            )

    # 2. Cross-Repo UI HTTP Service <-> Backend API Gateway <-> Lambda Handlers
    sai_root = repo_map.get('standard-acquisition-interface')
    nif_root = repo_map.get('national-item-file-maintenance')
    infra_root = repo_map.get('infrastructure')
    ui_root = repo_map.get('supply-chain-user-interface')

    if sai_root and (sai_root / 'lib/apigateway.ts').is_file():
        sai_apigw_path = sai_root / 'lib/apigateway.ts'
        if ui_root and (ui_root / 'angular/fss-ui/src/app/sai-workspace/sai.service.ts').is_file():
            sai_svc_rel = 'angular/fss-ui/src/app/sai-workspace/sai.service.ts'
            sai_svc_path = ui_root / sai_svc_rel
            for method_name, route_str, apigw_pat, target_lam in [
                ('searchRejectedPurchaseOrders', 'GET /pocorrection/list', r"addResource\('list'\)", 'sai-get-purchase-order'),
                ('getCorrectionByPoNumber', 'GET /pocorrection/{poNumber}', r"poCorrectionPoNumberResource\.addMethod\('GET'", 'sai-get-purchase-order'),
                ('submitCorrection', 'PUT /pocorrection/{poNumber}', r"poCorrectionPoNumberResource\.addMethod\('PUT'", 'sai-update-purchase-order'),
            ]:
                add_seam(
                    'ui_to_apigw_route',
                    'supply-chain-user-interface',
                    sai_svc_rel,
                    _find_line(sai_svc_path, method_name),
                    f'SAIService.{method_name}',
                    'standard-acquisition-interface',
                    'lib/apigateway.ts',
                    _find_line(sai_apigw_path, apigw_pat),
                    f'SaiApiGateway:{route_str}',
                    route_str,
                    f'Angular SAIService.{method_name} -> S206 API Gateway {route_str} -> {target_lam}',
                )

        for route_str, apigw_pat, lam_rel, sym, detail in [
            (
                'GET /pocorrection/list',
                r'purchaseOrderListResource\.addMethod',
                'assets/lambda/sai-get-purchase-order/index.ts',
                'sai-get-purchase-order.handler',
                'API Gateway GET /pocorrection/list invokes sai-get-purchase-order/index.ts',
            ),
            (
                'GET /pocorrection/{poNumber}',
                r'purchaseOrderResource\.addMethod\(\s*["\']GET["\']',
                'assets/lambda/sai-get-purchase-order/index.ts',
                'sai-get-purchase-order.handler',
                'API Gateway GET /pocorrection/{poNumber} (and /serviceauth/pocorrection/{poNumber}) invokes sai-get-purchase-order/index.ts',
            ),
            (
                'PUT /pocorrection/{poNumber}',
                r'purchaseOrderResource\.addMethod\(\s*["\']PUT["\']',
                'assets/lambda/sai-update-purchase-order/index.ts',
                'sai-update-purchase-order.handler',
                'API Gateway PUT /pocorrection/{poNumber} invokes sai-update-purchase-order/index.ts (sets status B1, clears errors, sends SQS message)',
            ),
            (
                'DELETE /pocorrection/{poNumber}',
                r'purchaseOrderResource\.addMethod\(\s*["\']DELETE["\']',
                'assets/lambda/sai-delete-purchase-order/index.ts',
                'sai-delete-purchase-order.handler [ROUTE_MISMATCH]',
                'DEFECT/INCONSISTENCY: lib/apigateway.ts:L157 wires DELETE /pocorrection/{poNumber} to deletePurchaseOrderFn (sai-delete-purchase-order/index.ts:L21-63), which only has GET and PUT branches and NO DELETE branch (always returns 404).',
            ),
        ]:
            lam_path = sai_root / lam_rel
            if lam_path.is_file():
                add_seam(
                    'apigw_to_lambda',
                    'standard-acquisition-interface',
                    'lib/apigateway.ts',
                    _find_line(sai_apigw_path, apigw_pat),
                    f'SaiApiGateway:{route_str}',
                    'standard-acquisition-interface',
                    lam_rel,
                    _find_line(lam_path, r'export const handler|httpMethod'),
                    sym,
                    route_str,
                    detail,
                )

        # Async Kinesis & SQS seams in S206
        proc_rel = 'assets/lambda/sai-purchase-order-processor/index.ts'
        peg_rel = 'assets/lambda/sai-pegasys-io-data-processor/processor/pegasysIOCreateUpdateProcessor.ts'
        if (sai_root / proc_rel).is_file():
            add_seam(
                'async_event_flow',
                'standard-acquisition-interface',
                'lib/apigateway.ts',
                _find_line(sai_apigw_path, r'PutRecord'),
                'SaiApiGateway:/po:POST (Kinesis PutRecord)',
                'standard-acquisition-interface',
                proc_rel,
                _find_line(sai_root / proc_rel, r'export const handler'),
                'sai-purchase-order-processor.handler',
                'Kinesis:poDataStream -> sai-purchase-order-processor',
                'API Gateway /po integrates with Kinesis PutRecord (lib/stream.ts: on-demand, TRIM_HORIZON, batchSize 100, retryAttempts 3, onFailure destination in lib/functions.ts without bisectBatchOnError/reportBatchItemFailures) -> sai-purchase-order-processor writes DynamoDB and sends SQS message.',
            )
        if (sai_root / proc_rel).is_file() and (sai_root / peg_rel).is_file():
            add_seam(
                'async_event_flow',
                'standard-acquisition-interface',
                proc_rel,
                _find_line(sai_root / proc_rel, r'sendMessage|sqs'),
                'sai-purchase-order-processor.handler',
                'standard-acquisition-interface',
                peg_rel,
                _find_line(sai_root / peg_rel, r'batchItemFailures'),
                'sai-pegasys-io-data-processor [BATCH_FAILURE_MISMATCH]',
                'SQS:pegasysIOQueue -> sai-pegasys-io-data-processor',
                'SQS queue (lib/functions.ts SqsEventSource batchSize 10) triggers sai-pegasys-io-data-processor. MISMATCH: pegasysIOCreateUpdateProcessor.ts returns { batchItemFailures }, but lib/functions.ts SqsEventSource omits reportBatchItemFailures: true.',
            )

    # 3. Cross-Repo S207 (UI) <-> S204 (Infrastructure CDK) <-> S205 (NIF Lambdas)
    if infra_root:
        s204_nif_stack_rel = 'services/national-item-file-maintenance/infrastructure/cdk/src/nsn-service-stack.ts'
        s204_nif_importer_rel = 'services/national-item-file-maintenance/infrastructure/cdk/src/helper/CrossStackImporter.ts'
        s204_nif_stack_path = infra_root / s204_nif_stack_rel
        s204_nif_importer_path = infra_root / s204_nif_importer_rel
        nif_svc_rel = 'angular/fss-ui/src/app/api-service/nif.service.ts'
        nif_svc_path = ui_root / nif_svc_rel if ui_root else None

        nif_routes = [
            ('getNSNServiceData', 'GET /nsnservice/v1/details/{nsn}', 'get-nsn-service-details', 'functions/get-nsn-service-details/src/processor/get-nsn-service-details.ts', 'Authorizes read via shared/utils/nsn-data-util.ts and enriches lookup descriptions.'),
            ('getNSNMetadata', 'GET /nsnservice/v1/lookup', 'get-nsn-service-lookup', 'functions/get-nsn-service-lookup/src/processor/get-nsn-service-lookup.ts', 'Returns all lookup lists or a named subset.'),
            ('createNSNServiceData', 'POST /nsnservice/v1/details', 'create-nsn-service-details', 'functions/create-nsn-service-details/src/processor/create-nsn-service-details.ts', 'Writes NIF/NDF items and sends non-atomic LM/FLDF notification via shared/api/api-client.ts.'),
            ('updateNSNServiceData', 'PUT /nsnservice/v1/details/{nsn}', 'update-nsn-service-details', 'functions/update-nsn-service-details/src/processor/update-nsn-service-details.ts', 'Updates NSN details in NIF/NDF.'),
            ('deleteNSNService', 'DELETE /nsnservice/v1/details/{nsn}', 'delete-nsn-service-details', 'functions/delete-nsn-service-details/src/processor/delete-nsn-service-details.ts', 'Deletes NSN service details.'),
            ('massBuyerUpdate', 'PUT /nsnservice/v1/buyer/massupdate', 'buyer-mass-update-details', 'functions/buyer-mass-update-details/src/processor/buyer-mass-update-details.ts', 'Queries buyer-indexed NIF records via shared/utils/dynamo.ts queryItemsByBuyerIndex (unpaginated LastEvaluatedKey).'),
        ]
        if s204_nif_stack_path.is_file():
            for ui_method, route_str, pkg_name, s205_target_rel, desc in nif_routes:
                if nif_svc_path and nif_svc_path.is_file():
                    add_seam(
                        'ui_to_apigw_route',
                        'supply-chain-user-interface',
                        nif_svc_rel,
                        _find_line(nif_svc_path, ui_method),
                        f'NIFService.{ui_method}',
                        'infrastructure',
                        s204_nif_stack_rel,
                        _find_line(s204_nif_stack_path, pkg_name.replace('-', '_').upper()),
                        f'NsnServiceStack:{route_str}',
                        route_str,
                        f'Cross-repo UI -> Infra CDK: S207 NIFService.{ui_method} calls {route_str} defined in S204 {s204_nif_stack_rel}',
                    )
                if nif_root and (nif_root / s205_target_rel).is_file():
                    add_seam(
                        'apigw_to_lambda',
                        'infrastructure',
                        s204_nif_stack_rel,
                        _find_line(s204_nif_stack_path, r'createLambda|NodejsFunction|Function'),
                        f'NsnServiceStack:{route_str}',
                        'national-item-file-maintenance',
                        s205_target_rel,
                        1,
                        f'{pkg_name}.processor',
                        route_str,
                        f'Cross-repo Infra CDK -> S205 Lambda: {route_str} routes to S205 {s205_target_rel}. {desc}',
                    )

        if s204_nif_importer_path.is_file():
            target_repo = 'national-item-file-maintenance' if nif_root else 'infrastructure'
            target_path = 'functions/nif-file-processor/src/index.ts' if nif_root else s204_nif_stack_rel
            add_seam(
                'cfn_cross_stack_import',
                'infrastructure',
                s204_nif_importer_rel,
                _find_line(s204_nif_importer_path, r'importValue|valueForStringParameter'),
                'CrossStackImporter',
                target_repo,
                target_path,
                1,
                'S205_File_And_Export_Processors',
                'Fn.importValue+SSM:ScannedCleanInputBucket+StateMachine+VPC+Transfer',
                'S204 CrossStackImporter.ts imports Fn.importValue(${env}-falcon-infra-stack:ExportsOutputRefFalconScannedCleanInputS3Bucket78388202819115CA), Step Functions state machine, artifact bucket, API Gateway, VPC, and transfer references for S205 processors.',
            )

    # 4. Generic CloudFormation Fn.importValue / CrossStackImporter & Canary Pattern Seams across any other supplied repos
    for c_repo, c_path, c_rel, c_text in cdk_files:
        if 'CrossStackImporter.ts' not in c_rel and 'Fn.importValue' in c_text:
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
                '@gsa/cdk-patterns:NodejsVersioned',
                'canary:blueGreen',
                f'{c_repo}:{c_rel}:L{line_no} configures @gsa/cdk-patterns blueGreen / trafficShifting deployment seam.',
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
