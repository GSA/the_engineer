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
            if h_name == 'sai-delete-purchase-order':
                del_entry = h['root'] / h['entry_rel']
                apigw_file = h['root'] / 'lib/apigateway.ts'
                apigw_has_delete = (
                    apigw_file.is_file()
                    and _find_line_optional(apigw_file, r'addMethod\(\s*["\']DELETE["\']') is not None
                )
                if (
                    apigw_has_delete
                    and del_entry.is_file()
                    and '"DELETE"' not in _read_text(del_entry)
                    and "'DELETE'" not in _read_text(del_entry)
                ):
                    notes.append(
                        'ROUTE_MISMATCH: lib/apigateway.ts wires DELETE /pocorrection/{poNumber} to '
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
            orphan_notes = [
                f"{h['dir_rel']} exists in {h['repo']} source tree but is NEVER referenced in any CDK construct or infrastructure stack."
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
    seen_cfn_files: set[tuple[str, str]] = set()

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
                ('searchRejectedPurchaseOrders', 'GET /pocorrection/list', r"addResource\(['\"]list['\"]\)|pocorrection", 'sai-get-purchase-order'),
                ('getCorrectionByPoNumber', 'GET /pocorrection/{poNumber}', r"poCorrectionPoNumberResource\.addMethod\(['\"]GET['\"]|purchaseOrderResource\.addMethod\(\s*['\"]GET['\"]", 'sai-get-purchase-order'),
                ('submitCorrection', 'PUT /pocorrection/{poNumber}', r"poCorrectionPoNumberResource\.addMethod\(['\"]PUT['\"]|purchaseOrderResource\.addMethod\(\s*['\"]PUT['\"]", 'sai-update-purchase-order'),
            ]:
                ui_line = _find_line_optional(sai_svc_path, rf'\b{re.escape(method_name)}\b')
                apigw_line = _find_line_optional(sai_apigw_path, apigw_pat)
                if ui_line is not None and apigw_line is not None:
                    seen_route_keys.add(('supply-chain-user-interface', sai_svc_rel, route_str))
                    add_seam(
                        'ui_to_apigw_route',
                        'supply-chain-user-interface',
                        sai_svc_rel,
                        ui_line,
                        f'SAIService.{method_name}',
                        'standard-acquisition-interface',
                        'lib/apigateway.ts',
                        apigw_line,
                        f'SaiApiGateway:{route_str}',
                        route_str,
                        f'Angular SAIService.{method_name} -> S206 API Gateway {route_str} -> {target_lam}',
                    )

        for verb, route_str, apigw_pat, lam_rel, base_sym, base_detail in [
            (
                'GET',
                'GET /pocorrection/list',
                r'purchaseOrderListResource\.addMethod',
                'assets/lambda/sai-get-purchase-order/index.ts',
                'sai-get-purchase-order.handler',
                'API Gateway GET /pocorrection/list invokes sai-get-purchase-order/index.ts',
            ),
            (
                'GET',
                'GET /pocorrection/{poNumber}',
                r'(?:purchaseOrderResource|poCorrectionPoNumberResource)\.addMethod\(\s*["\']GET["\']',
                'assets/lambda/sai-get-purchase-order/index.ts',
                'sai-get-purchase-order.handler',
                'API Gateway GET /pocorrection/{poNumber} (and /serviceauth/pocorrection/{poNumber}) invokes sai-get-purchase-order/index.ts',
            ),
            (
                'PUT',
                'PUT /pocorrection/{poNumber}',
                r'(?:purchaseOrderResource|poCorrectionPoNumberResource)\.addMethod\(\s*["\']PUT["\']',
                'assets/lambda/sai-update-purchase-order/index.ts',
                'sai-update-purchase-order.handler',
                'API Gateway PUT /pocorrection/{poNumber} invokes sai-update-purchase-order/index.ts (sets status B1, clears errors, sends SQS message)',
            ),
            (
                'DELETE',
                'DELETE /pocorrection/{poNumber}',
                r'(?:purchaseOrderResource|poCorrectionPoNumberResource)\.addMethod\(\s*["\']DELETE["\']',
                'assets/lambda/sai-delete-purchase-order/index.ts',
                'sai-delete-purchase-order.handler',
                'API Gateway DELETE /pocorrection/{poNumber} invokes sai-delete-purchase-order/index.ts',
            ),
        ]:
            apigw_line = _find_line_optional(sai_apigw_path, apigw_pat)
            lam_path = sai_root / lam_rel
            if apigw_line is not None and lam_path.is_file():
                lam_text = _read_text(lam_path)
                sym = base_sym
                detail = base_detail
                if (
                    re.search(r'httpMethod', lam_text)
                    and not re.search(rf"""['"]{verb}['"]""", lam_text)
                ):
                    sym = f'{base_sym} [ROUTE_MISMATCH]'
                    detail = (
                        f'DEFECT/INCONSISTENCY: lib/apigateway.ts:L{apigw_line} wires {route_str} to '
                        f'{lam_rel}, which checks httpMethod for other verbs but has NO {verb} branch (returns 404).'
                    )
                seen_apigw_keys.add(('standard-acquisition-interface', 'lib/apigateway.ts', route_str))
                add_seam(
                    'apigw_to_lambda',
                    'standard-acquisition-interface',
                    'lib/apigateway.ts',
                    apigw_line,
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
        put_record_line = _find_line_optional(sai_apigw_path, r'PutRecord')
        if put_record_line is not None and (sai_root / proc_rel).is_file():
            seen_async_keys.add(('standard-acquisition-interface', 'lib/apigateway.ts', proc_rel))
            add_seam(
                'async_event_flow',
                'standard-acquisition-interface',
                'lib/apigateway.ts',
                put_record_line,
                'SaiApiGateway:/po:POST (Kinesis PutRecord)',
                'standard-acquisition-interface',
                proc_rel,
                _find_line(sai_root / proc_rel, r'export const handler'),
                'sai-purchase-order-processor.handler',
                'Kinesis:poDataStream -> sai-purchase-order-processor',
                'API Gateway /po integrates with Kinesis PutRecord (lib/stream.ts: on-demand, TRIM_HORIZON, batchSize 100, retryAttempts 3, onFailure destination in lib/functions.ts without bisectBatchOnError/reportBatchItemFailures) -> sai-purchase-order-processor writes DynamoDB and sends SQS message.',
            )
        if (sai_root / proc_rel).is_file() and (sai_root / peg_rel).is_file():
            send_line = _find_line_optional(sai_root / proc_rel, r'sendMessage|sqs')
            peg_line = _find_line_optional(sai_root / peg_rel, r'batchItemFailures|export')
            fns_text = _read_text(sai_root / 'lib/functions.ts')
            has_batch_failures = 'batchItemFailures' in _read_text(sai_root / peg_rel)
            reports_batch_failures = bool(re.search(r'reportBatchItemFailures\s*:\s*true', fns_text))
            if send_line is not None and peg_line is not None:
                seen_async_keys.add(('standard-acquisition-interface', proc_rel, peg_rel))
                mismatch = has_batch_failures and not reports_batch_failures
                add_seam(
                    'async_event_flow',
                    'standard-acquisition-interface',
                    proc_rel,
                    send_line,
                    'sai-purchase-order-processor.handler',
                    'standard-acquisition-interface',
                    peg_rel,
                    peg_line,
                    'sai-pegasys-io-data-processor [BATCH_FAILURE_MISMATCH]' if mismatch else 'sai-pegasys-io-data-processor',
                    'SQS:pegasysIOQueue -> sai-pegasys-io-data-processor',
                    (
                        'SQS queue (lib/functions.ts SqsEventSource batchSize 10) triggers sai-pegasys-io-data-processor. '
                        'MISMATCH: pegasysIOCreateUpdateProcessor.ts returns { batchItemFailures }, '
                        'but lib/functions.ts SqsEventSource omits reportBatchItemFailures: true.'
                        if mismatch
                        else 'SQS queue (lib/functions.ts SqsEventSource) triggers sai-pegasys-io-data-processor with reportBatchItemFailures enabled.'
                    ),
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
                stack_pat = rf'{pkg_name.replace("-", "_").upper()}|{re.escape(pkg_name)}'
                stack_line = _find_line_optional(s204_nif_stack_path, stack_pat)
                if nif_svc_path and nif_svc_path.is_file():
                    ui_line = _find_line_optional(nif_svc_path, rf'\b{re.escape(ui_method)}\b')
                    if ui_line is not None and stack_line is not None:
                        seen_route_keys.add(('supply-chain-user-interface', nif_svc_rel, route_str))
                        add_seam(
                            'ui_to_apigw_route',
                            'supply-chain-user-interface',
                            nif_svc_rel,
                            ui_line,
                            f'NIFService.{ui_method}',
                            'infrastructure',
                            s204_nif_stack_rel,
                            stack_line,
                            f'NsnServiceStack:{route_str}',
                            route_str,
                            f'Cross-repo UI -> Infra CDK: S207 NIFService.{ui_method} calls {route_str} defined in S204 {s204_nif_stack_rel}',
                        )
                if stack_line is not None and nif_root and (nif_root / s205_target_rel).is_file():
                    seen_apigw_keys.add(('infrastructure', s204_nif_stack_rel, route_str))
                    add_seam(
                        'apigw_to_lambda',
                        'infrastructure',
                        s204_nif_stack_rel,
                        stack_line,
                        f'NsnServiceStack:{route_str}',
                        'national-item-file-maintenance',
                        s205_target_rel,
                        1,
                        f'{pkg_name}.processor',
                        route_str,
                        f'Cross-repo Infra CDK -> S205 Lambda: {route_str} routes to S205 {s205_target_rel}. {desc}',
                    )

        if s204_nif_importer_path.is_file():
            imp_line = _find_line_optional(s204_nif_importer_path, r'importValue|valueForStringParameter')
            if imp_line is not None:
                seen_cfn_files.add(('infrastructure', s204_nif_importer_rel))
                target_repo = 'national-item-file-maintenance' if nif_root else 'infrastructure'
                target_path = 'functions/nif-file-processor/src/index.ts' if nif_root else s204_nif_stack_rel
                add_seam(
                    'cfn_cross_stack_import',
                    'infrastructure',
                    s204_nif_importer_rel,
                    imp_line,
                    'CrossStackImporter',
                    target_repo,
                    target_path,
                    1,
                    'S205_File_And_Export_Processors',
                    'Fn.importValue+SSM:ScannedCleanInputBucket+StateMachine+VPC+Transfer',
                    'S204 CrossStackImporter.ts imports Fn.importValue(${env}-falcon-infra-stack:ExportsOutputRefFalconScannedCleanInputS3Bucket78388202819115CA), Step Functions state machine, artifact bucket, API Gateway, VPC, and transfer references for S205 processors.',
                )

    # 4. Generic content-driven UI -> API Gateway, API Gateway -> Lambda, Async SQS, and CloudFormation seams across ANY repositories
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
                            f"DEFECT/INCONSISTENCY: {c_repo}:{c_rel}:L{line_no} wires {route_str} to "
                            f"{h['repo']}:{h['entry_rel']}, which checks httpMethod for other verbs "
                            f"but has NO {verb} branch."
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
                    if key in seen_async_keys or ('standard-acquisition-interface', 'assets/lambda/sai-purchase-order-processor/index.ts', 'assets/lambda/sai-pegasys-io-data-processor/processor/pegasysIOCreateUpdateProcessor.ts') in seen_async_keys and c_repo == 'standard-acquisition-interface':
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
                            f"MISMATCH: {h['repo']}:{h['entry_rel']} returns batchItemFailures, "
                            f"but {c_repo}:{c_rel}:L{line_no} SqsEventSource omits reportBatchItemFailures: true."
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

    # 5. Generic CloudFormation Fn.importValue & Canary Pattern Seams across any supplied repos
    for c_repo, c_path, c_rel, c_text in cdk_files:
        if (c_repo, c_rel) not in seen_cfn_files and 'Fn.importValue' in c_text:
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
