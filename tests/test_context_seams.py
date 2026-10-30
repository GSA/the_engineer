"""Tests for cross-repository seam scanning and optional knowitall retirement."""
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

    def test_detects_ui_to_cdk_to_lambda_seams_and_defects(self):
        # Angular UI service calling PUT /buyer/massupdate and /pocorrection
        self._write(
            "supply-chain-user-interface/angular/fss-ui/src/app/api-service/nif.service.ts",
            "const BaseUrl = `${environment.NIF_API_URL}/nsnservice/v1`;\n"
            "export class NIFService {\n"
            "  massBuyerUpdate(http: any, body: any) { return http.put(BaseUrl + '/buyer/massupdate', body); }\n"
            "}\n",
        )
        self._write(
            "supply-chain-user-interface/angular/fss-ui/src/app/sai-workspace/sai.service.ts",
            "export class SAIService {\n"
            "  searchRejectedPurchaseOrders() { return '/pocorrection/list'; }\n"
            "}\n",
        )
        # Infrastructure CDK repo defining /buyer/massupdate and CrossStackImporter
        self._write(
            "infrastructure/services/national-item-file-maintenance/infrastructure/cdk/src/models/constants.ts",
            "export const PUT_BUYER_MASS_UPDATE_DETAILS = {\n"
            "  name: 'buyer-mass-update-details',\n"
            "  handler: 'index.buyerMassUpdateHandler',\n"
            "  artifactPath: 'services/national-item-file-maintenance/buyer-mass-update-details/index.zip',\n"
            "};\n",
        )
        self._write(
            "infrastructure/services/national-item-file-maintenance/infrastructure/cdk/src/nsn-service-stack.ts",
            "export class NsnApiStack {\n"
            "  createLambda() { return 'BUYER_MASS_UPDATE_DETAILS'; }\n"
            "}\n",
        )
        self._write(
            "infrastructure/services/national-item-file-maintenance/infrastructure/cdk/src/helper/CrossStackImporter.ts",
            "import * as cdk from 'aws-cdk-lib';\n"
            "export const v = cdk.Fn.importValue('fss19-vpc');\n",
        )
        # Backend repo with active handler, stub handler, and orphan Lambda directory
        self._write(
            "national-item-file-maintenance/functions/buyer-mass-update-details/src/processor/buyer-mass-update-details.ts",
            "export async function buyerMassUpdateHandler(event: any) { return { statusCode: 200 }; }\n",
        )
        self._write(
            "national-item-file-maintenance/functions/polines-file-processor/src/index.ts",
            "export async function handler() { return { message: 'polinesFileProcessor not in use anymore' }; }\n",
        )
        self._write(
            "standard-acquisition-interface/lib/apigateway.ts",
            "export class SaiApi {\n"
            "  wire() {\n"
            "    const p = 'pocorrection';\n"
            "    const s = 'serviceauth';\n"
            "    const k = 'PutRecord';\n"
            "    return [p, s, k];\n"
            "  }\n"
            "}\n",
        )
        self._write(
            "standard-acquisition-interface/lib/functions.ts",
            "export class SaiFns {\n"
            "  init() {\n"
            "    const a = '../assets/lambda/sai-get-purchase-order/index.ts';\n"
            "    const b = '../assets/lambda/sai-delete-purchase-order/index.ts';\n"
            "    const c = 'trafficShifting';\n"
            "    return [a, b, c];\n"
            "  }\n"
            "}\n",
        )
        self._write(
            "standard-acquisition-interface/assets/lambda/sai-get-purchase-order/index.ts",
            "export const handler = async (event: any) => ({ statusCode: 200 });\n",
        )
        self._write(
            "standard-acquisition-interface/assets/lambda/sai-delete-purchase-order/index.ts",
            "export const handler = async (event: any) => {\n"
            "  if (event.httpMethod === 'PUT') return { statusCode: 200 };\n"
            "  return { statusCode: 404 };\n"
            "};\n",
        )
        self._write(
            "standard-acquisition-interface/assets/lambda/orphan-lambda/index.ts",
            "export const handler = async () => ({});\n",
        )

        repo_map = resolve_repositories(workspace_root=str(self.root))
        seams = scan_seams(repo_map)
        kinds = {s["seam_kind"] for s in seams}
        self.assertIn("ui_to_apigw_route", kinds)
        self.assertIn("apigw_to_lambda", kinds)
        self.assertIn("cdk_wires_lambda", kinds)
        self.assertIn("orphan_lambda_directory", kinds)
        self.assertIn("cfn_cross_stack_import", kinds)
        self.assertIn("canary_and_pattern_config", kinds)

        filtered = filter_seams(seams, query="orphan-lambda")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["seam_kind"], "orphan_lambda_directory")

        json_out = json.loads(render_seams(repo_map, seams, fmt="json", max_chars=20000))
        self.assertEqual(json_out["schema"], "engineer.cross-repo-seams/v1")

        md = render_seams(repo_map, seams, fmt="markdown", max_chars=20000)
        self.assertIn("# Cross-Repository Seam Map", md)
        self.assertIn("orphan_lambda_directory", md)

        compact = render_seams(repo_map, seams, fmt="compact", max_chars=800)
        self.assertLessEqual(len(compact), 800)
