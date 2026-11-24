"""Tests for the dependency-free cross-repository seam scanner."""
import json
from pathlib import Path
import tempfile
import unittest

from engineer_context.seams import filter_seams, render_seams, resolve_repositories, scan_seams


class SeamScannerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def _write(self, rel_path: str, content: str) -> Path:
        target = self.root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def test_detects_cdk_lambda_orphan_import_and_canary_seams(self):
        self._write(
            "acme-portal-ui/src/services/orders.service.ts",
            "export class OrdersService {\n"
            "  cancel() { return this.http.delete('/orders/cancel'); }\n"
            "}\n",
        )
        self._write(
            "acme-order-service/lib/stack.ts",
            "const orderCancel = createLambda('order-cancel');\n"
            "const ordersRes = api.root.addResource('orders')\n"
            "const cancelRes = ordersRes.addResource('cancel')\n"
            "cancelRes.addMethod('DELETE', new LambdaIntegration(orderCancel));\n"
            "const imported = Fn.importValue('shared-bucket-export');\n"
            "const shift = 'trafficShifting';\n",
        )
        self._write(
            "acme-order-service/functions/order-cancel/index.ts",
            "export const handler = async (event: any) => {\n"
            "  if (event.httpMethod === 'DELETE') return { statusCode: 200 };\n"
            "  return { statusCode: 404 };\n"
            "};\n",
        )
        self._write(
            "acme-order-service/functions/order-legacy/index.ts",
            "export const handler = async () => ({ message: 'order-legacy not in use anymore' });\n",
        )

        repo_map = resolve_repositories(workspace_root=str(self.root))
        seams = scan_seams(repo_map)
        kinds = {s["seam_kind"] for s in seams}
        self.assertEqual(
            kinds,
            {
                "ui_to_apigw_route", "apigw_to_lambda", "cdk_wires_lambda",
                "orphan_lambda_directory", "cfn_cross_stack_import", "canary_and_pattern_config",
            },
        )

        filtered = filter_seams(seams, query="order-legacy")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["seam_kind"], "orphan_lambda_directory")
        self.assertIn("DEPRECATED MARKER", filtered[0]["detail"])

        json_out = json.loads(render_seams(repo_map, seams, fmt="json", max_chars=20000))
        self.assertEqual(json_out["schema"], "engineer.cross-repo-seams/v1")

        md = render_seams(repo_map, seams, fmt="markdown", max_chars=20000)
        self.assertIn("# Cross-Repository Seam Map", md)
        self.assertIn("orphan_lambda_directory", md)

        compact = render_seams(repo_map, seams, fmt="compact", max_chars=800)
        self.assertLessEqual(len(compact), 800)

        with self.assertRaises(ValueError):
            render_seams(repo_map, seams, fmt="json", max_chars=10)

    def test_detail_is_derived_from_scanned_files_only(self):
        self._write(
            "svc/lib/stack.ts",
            "const upd = createLambda('order-update');\n"
            "api.root.addMethod('PUT', new LambdaIntegration(orderUpdate));\n"
            "stream.addEventSource(new SqsEventSource(q, { batchSize: 5 }));\n"
            "await kinesis.PutRecord({});\n",
        )
        handler = self._write(
            "svc/functions/order-update/index.ts",
            "export const handler = async (event: any) => {\n"
            "  if (event.httpMethod === 'PUT') return { statusCode: 200 };\n"
            "  return { statusCode: 404 };\n"
            "};\n",
        )

        def details():
            repo_map = resolve_repositories(repos=[self.root / "svc"])
            return " ".join(s["detail"] for s in scan_seams(repo_map))

        before = details()
        self.assertNotIn("MISMATCH", before)
        # Static claims about behavior the scanner never read must not appear.
        for claim in ("TRIM_HORIZON", "bisectBatchOnError", "sets status", "NEVER referenced"):
            self.assertNotIn(claim, before)

        handler.write_text(
            "export const handler = async (event: any) => {\n"
            "  if (event.httpMethod === 'GET') return { statusCode: 200 };\n"
            "  return { statusCode: 404 };\n"
            "};\n",
            encoding="utf-8",
        )
        self.assertIn("POSSIBLE MISMATCH", details())

    def test_content_driven_extraction_avoids_false_positives_and_supports_generic_repos(self):
        # 1. A handled DELETE and reportBatchItemFailures: true emit no false mismatch
        self._write(
            "billing-service/lib/functions.ts",
            "const fn = createLambda('invoice-delete');\n"
            "const proc = createLambda('invoice-processor');\n"
            "const ledger = createLambda('ledger-writer');\n"
            "ledger.addEventSource(new SqsEventSource(queue, { batchSize: 10, reportBatchItemFailures: true }));\n",
        )
        self._write(
            "billing-service/lib/apigateway.ts",
            "invoiceResource.addMethod('DELETE', new LambdaIntegration(invoiceDeleteFn));\n",
        )
        self._write(
            "billing-service/assets/lambda/invoice-delete/index.ts",
            "export const handler = async (event: any) => {\n"
            "  if (event.httpMethod === 'DELETE') return { statusCode: 200 };\n"
            "  return { statusCode: 404 };\n"
            "};\n",
        )
        self._write(
            "billing-service/assets/lambda/invoice-processor/index.ts",
            "export const handler = async () => { await sqs.sendMessage({}); };\n",
        )
        self._write(
            "billing-service/assets/lambda/ledger-writer/processor/writer.ts",
            "export const process = async () => ({ batchItemFailures: [] });\n",
        )
        self._write(
            "billing-service/assets/lambda/legacy-export/index.ts",
            "export const handler = async () => {\n"
            "  return { statusCode: 200, body: JSON.stringify('legacy export not in use anymore') };\n"
            "};\n",
        )
        # Ensure SKIP_DIRS (node_modules) are pruned during walk
        self._write(
            "billing-service/node_modules/pkg/ignored.ts",
            "Fn.importValue('should-never-be-scanned');\n",
        )
        # 2. Arbitrarily named repos + CrossStackImporter.ts in a non-infrastructure repo
        self._write(
            "acme-portal-ui/src/services/orders.service.ts",
            "export class OrdersService {\n"
            "  cancel() { return this.http.delete('/orders/cancel'); }\n"
            "  list() { return this.http.get('/preorders'); }\n"
            "}\n",
        )
        self._write(
            "acme-order-service/lib/stack.ts",
            "const orderCancel = createLambda('order-cancel');\n"
            "const orderAudit = createLambda('order-audit');\n"
            "const ordersRes = api.root.addResource('orders')\n"
            "const cancelRes = ordersRes.addResource('cancel')\n"
            "cancelRes.addMethod('DELETE', new LambdaIntegration(orderCancel));\n"
            "orderCancel.addEventSource(new SqsEventSource(q, { batchSize: 5 }));\n",
        )
        self._write(
            "acme-order-service/functions/order-audit/index.ts",
            "export const handler = async () => ({ statusCode: 200, batchItemFailures: [] });\n",
        )
        self._write(
            "acme-order-service/lib/helper/CrossStackImporter.ts",
            "export const bucket = Fn.importValue('shared-bucket-export');\n",
        )
        self._write(
            "acme-order-service/functions/order-cancel/index.ts",
            "export const handler = async (event: any) => {\n"
            "  if (event.httpMethod === 'GET') return { statusCode: 200, batchItemFailures: [] };\n"
            "  return { statusCode: 404, batchItemFailures: [] };\n"
            "};\n",
        )

        repo_map = resolve_repositories(workspace_root=str(self.root))
        seams = scan_seams(repo_map)
        billing_seams = [s for s in seams if s["source_repo"] == "billing-service"]
        billing_md = render_seams(repo_map, billing_seams, fmt="markdown", max_chars=20000)
        self.assertNotIn("ROUTE_MISMATCH", billing_md)
        self.assertNotIn("BATCH_FAILURE_MISMATCH", billing_md)
        self.assertNotIn("POSSIBLE MISMATCH", billing_md)
        self.assertNotIn("should-never-be-scanned", billing_md)

        orphans = [s for s in billing_seams if s["seam_kind"] == "orphan_lambda_directory"]
        self.assertEqual(len(orphans), 1)
        self.assertIn("[STUB]", orphans[0]["source_symbol"])
        self.assertIn("DEPRECATED MARKER", orphans[0]["detail"])

        acme_seams = [s for s in seams if s["source_repo"].startswith("acme-")]
        acme_kinds = {s["seam_kind"] for s in acme_seams}
        self.assertIn("ui_to_apigw_route", acme_kinds)
        self.assertIn("apigw_to_lambda", acme_kinds)
        self.assertIn("async_event_flow", acme_kinds)
        self.assertIn("cfn_cross_stack_import", acme_kinds)
        acme_md = render_seams(repo_map, acme_seams, fmt="markdown", max_chars=20000)
        self.assertIn("POSSIBLE MISMATCH", acme_md)
        self.assertIn("BATCH_FAILURE_MISMATCH", acme_md)
        self.assertIn("CrossStackImporter.importValue", acme_md)

        ui_routes = {s["route_or_resource"] for s in acme_seams if s["seam_kind"] == "ui_to_apigw_route"}
        self.assertEqual(ui_routes, {"DELETE /orders/cancel"})
        sqs_targets = {s["target_path"] for s in acme_seams if s["seam_kind"] == "async_event_flow"}
        self.assertEqual(sqs_targets, {"functions/order-cancel/index.ts"})
