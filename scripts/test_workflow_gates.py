#!/usr/bin/env python3
"""Behavioral tests for prompt, temporary-plan, review, and publication gates (mpew)."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
MODULE_PATH = HERE / "workflow-gates.py"


def load_module():
    if not MODULE_PATH.is_file():
        raise FileNotFoundError(f"Missing implementation module: {MODULE_PATH}")
    spec = importlib.util.spec_from_file_location("workflow_gates", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
         text=True,
        capture_output=True,
    )
    return proc.stdout.strip()


def init_temp_repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    run_git(repo, "init", "-b", "main")
    run_git(repo, "config", "user.name", "Synthetic Tester")
    run_git(repo, "config", "user.email", "synthetic@example.invalid")
    (repo / ".gitignore").write_text(".local/\n", encoding="utf-8")
    (repo / "README.md").write_text("# Synthetic Repo\n", encoding="utf-8")
    (repo / "context").mkdir(parents=True, exist_ok=True)
    (repo / "context" / "status.md").write_text("# Status\n", encoding="utf-8")
    (repo / "context" / "prompt-drafts").mkdir(parents=True, exist_ok=True)
    (repo / "context" / "prompt-drafts" / "jira-refinement.example.md").write_text(
        "# Draft-only refinement example\n",
        encoding="utf-8",
    )
    run_git(repo, "add", ".gitignore", "README.md", "context/status.md", "context/prompt-drafts/jira-refinement.example.md")
    run_git(repo, "commit", "-m", "Initial baseline")
    return repo


class PromptSurfaceTests(unittest.TestCase):
    def test_private_pi_surface_loads_repo_policy_without_forge_override(self):
        gates = load_module()
        result = gates.evaluate_prompt_surface("private_pi")
        self.assertTrue(result["allowed"])
        self.assertEqual(result["surface"], "private_pi")
        self.assertFalse(result["forge_workspace_section_injected"])
        self.assertFalse(result["skill_overrides_active"])
        self.assertTrue(result["requires_owner_approval_for_push"])
        self.assertTrue(result["requires_human_merge"])

    def test_forge_workspace_surface_filters_ancestor_agents_and_injects_overrides(self):
        gates = load_module()
        result = gates.evaluate_prompt_surface("forge_workspace")
        self.assertTrue(result["allowed"])
        self.assertEqual(result["surface"], "forge_workspace")
        self.assertTrue(result["forge_workspace_section_injected"])
        self.assertTrue(result["ancestor_agents_filtered"])
        self.assertTrue(result["override_replaces_worktree_agents"])
        self.assertTrue(result["skill_overrides_active"])
        self.assertFalse(result["requires_owner_approval_for_push"])
        self.assertTrue(result["requires_human_merge"])

    def test_roborev_review_surface_enforces_no_mcp_no_skills_readonly_and_opposite_family(self):
        gates = load_module()
        result = gates.evaluate_prompt_surface(
            "roborev_review",
            coding_model="claude-opus-5.5",
            review_model="gemini-4-argon",
        )
        self.assertTrue(result["allowed"])
        self.assertIn("--no-mcp", result["required_flags"])
        self.assertIn("--no-skills", result["required_flags"])
        self.assertEqual(result["coding_family"], "claude")
        self.assertEqual(result["review_family"], "gemini")
        self.assertTrue(result["read_only"])
        self.assertFalse(result["forge_workspace_section_injected"])

        same_family = gates.evaluate_prompt_surface(
            "roborev_review",
            coding_model="claude-opus-5.5",
            review_model="claude-sonnet-5.5",
        )
        self.assertFalse(same_family["allowed"])
        self.assertIn("distinct", same_family["reason"])


class TemporaryPlanGateTests(unittest.TestCase):
    def test_blocks_staged_and_untracked_local_plans(self):
        gates = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            repo = init_temp_repo(Path(tmp))
            local_plan = repo / ".local" / "plans" / "2026-10-30-working.md"
            local_plan.parent.mkdir(parents=True, exist_ok=True)
            local_plan.write_text("# Working plan\n", encoding="utf-8")

            verdict = gates.check_temporary_plans(repo, base_ref="main")
            self.assertFalse(verdict["allowed"])
            self.assertIn(".local/plans/2026-10-30-working.md", verdict["violations"])

            local_plan.unlink()
            clean = gates.check_temporary_plans(repo, base_ref="main")
            self.assertTrue(clean["allowed"])
            self.assertEqual(clean["violations"], [])

    def test_blocks_already_tracked_superpowers_plan_in_branch_diff(self):
        gates = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            repo = init_temp_repo(Path(tmp))
            run_git(repo, "checkout", "-b", "kenn-forge/kata/synthetic")
            tracked_plan = repo / "docs" / "superpowers" / "plans" / "2026-10-30-synthetic.md"
            tracked_plan.parent.mkdir(parents=True, exist_ok=True)
            tracked_plan.write_text("# Committed plan artifact\n", encoding="utf-8")
            run_git(repo, "add", "docs/superpowers/plans/2026-10-30-synthetic.md")

            staged_verdict = gates.check_temporary_plans(repo, base_ref="main")
            self.assertFalse(staged_verdict["allowed"])
            self.assertIn("docs/superpowers/plans/2026-10-30-synthetic.md", staged_verdict["staged_violations"])

            run_git(repo, "commit", "-m", "Accidental plan commit")
            branch_verdict = gates.check_temporary_plans(repo, base_ref="main")
            self.assertFalse(branch_verdict["allowed"])
            self.assertIn("docs/superpowers/plans/2026-10-30-synthetic.md", branch_verdict["branch_violations"])

            run_git(repo, "rm", "docs/superpowers/plans/2026-10-30-synthetic.md")
            run_git(repo, "commit", "-m", "Remove temporary plan before delivery")
            cleaned = gates.check_temporary_plans(repo, base_ref="main")
            self.assertTrue(cleaned["allowed"])

    def test_preserves_durable_docs_and_inactive_prompt_drafts(self):
        gates = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            repo = init_temp_repo(Path(tmp))
            run_git(repo, "checkout", "-b", "kenn-forge/kata/synthetic")
            (repo / "README.md").write_text("# Synthetic Repo\n\nShipped usage.\n", encoding="utf-8")
            (repo / "context" / "status.md").write_text("# Status\n\nUpdated milestone.\n", encoding="utf-8")
            (repo / "src").mkdir(exist_ok=True)
            (repo / "src" / "plan_spec_helper.py").write_text("VALUE = 1\n", encoding="utf-8")
            run_git(repo, "add", "README.md", "context/status.md", "src/plan_spec_helper.py")
            run_git(repo, "commit", "-m", "Update durable docs and code with plan/spec in filename")

            verdict = gates.check_temporary_plans(repo, base_ref="main")
            self.assertTrue(verdict["allowed"])
            self.assertEqual(verdict["violations"], [])
            self.assertTrue((repo / "context" / "prompt-drafts" / "jira-refinement.example.md").is_file())


class PublicationAndReviewGateTests(unittest.TestCase):
    def test_roborev_surface_blocks_all_mutations_and_publication(self):
        gates = load_module()
        for action in ("commit", "amend", "push_branch", "push_main", "pr_create", "pr_merge"):
            verdict = gates.evaluate_publication_gate(action, surface="roborev_review")
            self.assertFalse(verdict["allowed"], f"Expected roborev_review to block {action}")

    def test_private_pi_allows_local_commit_and_requires_owner_approval_for_push_and_pr(self):
        gates = load_module()
        commit_ok = gates.evaluate_publication_gate("commit", surface="private_pi", plans_clean=True)
        self.assertTrue(commit_ok["allowed"])

        push_blocked = gates.evaluate_publication_gate(
            "push_branch",
            surface="private_pi",
            plans_clean=True,
            owner_approved=False,
        )
        self.assertFalse(push_blocked["allowed"])
        self.assertIn("owner approval", push_blocked["reason"])

        push_approved = gates.evaluate_publication_gate(
            "push_branch",
            surface="private_pi",
            plans_clean=True,
            owner_approved=True,
        )
        self.assertTrue(push_approved["allowed"])

    def test_blocks_amend_of_reviewed_commit_and_requires_additive_fix(self):
        gates = load_module()
        amend_blocked = gates.evaluate_publication_gate(
            "amend",
            surface="forge_workspace",
            commit_sha="abc1234",
            reviewed_commits=["abc1234"],
        )
        self.assertFalse(amend_blocked["allowed"])
        self.assertIn("additive", amend_blocked["reason"])

    def test_blocks_publication_until_in_scope_findings_resolved_and_skipped_findings_justified(self):
        gates = load_module()
        unresolved = gates.evaluate_publication_gate(
            "push_branch",
            surface="forge_workspace",
            plans_clean=True,
            findings=[
                {"id": "F1", "in_scope": True, "confirmed": True, "disposition": "open"},
            ],
        )
        self.assertFalse(unresolved["allowed"])
        self.assertIn("F1", unresolved["reason"])

        unjustified_skip = gates.evaluate_publication_gate(
            "push_branch",
            surface="forge_workspace",
            plans_clean=True,
            findings=[
                {"id": "F2", "in_scope": False, "confirmed": False, "disposition": "skipped_invalid", "evidence": ""},
            ],
        )
        self.assertFalse(unjustified_skip["allowed"])
        self.assertIn("F2", unjustified_skip["reason"])

        resolved = gates.evaluate_publication_gate(
            "push_branch",
            surface="forge_workspace",
            plans_clean=True,
            findings=[
                {
                    "id": "F1",
                    "in_scope": True,
                    "confirmed": True,
                    "disposition": "fixed",
                    "fix_commit": "def5678",
                },
                {
                    "id": "F2",
                    "in_scope": False,
                    "confirmed": False,
                    "disposition": "skipped_invalid",
                    "evidence": "Checked synthetic_counter.py:42; negative step already rejected before addition.",
                },
            ],
        )
        self.assertTrue(resolved["allowed"])

    def test_human_merge_and_main_push_control(self):
        gates = load_module()
        agent_merge = gates.evaluate_publication_gate(
            "pr_merge",
            surface="forge_workspace",
            plans_clean=True,
            targets_registered=True,
            owner_approved=True,
            human_operator=False,
        )
        self.assertFalse(agent_merge["allowed"])
        self.assertIn("human", agent_merge["reason"])

        agent_main_push = gates.evaluate_publication_gate(
            "push_main",
            surface="forge_workspace",
            branch="main",
            plans_clean=True,
            owner_approved=True,
            human_operator=False,
        )
        self.assertFalse(agent_main_push["allowed"])

        human_merge = gates.evaluate_publication_gate(
            "pr_merge",
            surface="forge_workspace",
            plans_clean=True,
            targets_registered=True,
            human_operator=True,
        )
        self.assertTrue(human_merge["allowed"])


class SyntheticTaskDemoTests(unittest.TestCase):
    def test_run_synthetic_demo_executes_red_green_refactor_review_and_publication_gates(self):
        gates = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            private_dir = Path(tmp) / "private"
            private_dir.mkdir(mode=0o700)
            receipt_path = private_dir / "receipt.json"

            report = gates.run_synthetic_demo(receipt_path=receipt_path)
            self.assertEqual(report["schema"], "engineer.synthetic-gate-demo/v1")
            self.assertTrue(report["passed"])

            stages = report["stages"]
            self.assertTrue(stages["prompt_gates"]["passed"])
            self.assertFalse(stages["red"]["tests_passed"])
            self.assertNotEqual(stages["red"]["exit_code"], 0)
            self.assertTrue(stages["green"]["tests_passed"])
            self.assertTrue(stages["refactor"]["tests_passed"])
            self.assertNotEqual(stages["green"]["commit"], stages["refactor"]["commit"])

            review_stage = stages["review_gates"]
            self.assertFalse(review_stage["amend_reviewed_commit_allowed"])
            self.assertFalse(review_stage["unresolved_push_allowed"])
            self.assertTrue(review_stage["additive_fix_push_allowed"])
            self.assertNotEqual(review_stage["fix_commit"], stages["refactor"]["commit"])

            plan_stage = stages["plan_gates"]
            self.assertFalse(plan_stage["before_cleanup_allowed"])
            self.assertTrue(plan_stage["after_cleanup_allowed"])
            self.assertTrue(plan_stage["durable_docs_preserved"])

            pub_stage = stages["publication_gates"]
            self.assertFalse(pub_stage["private_pi_unapproved_push_allowed"])
            self.assertTrue(pub_stage["forge_branch_push_allowed"])
            self.assertTrue(pub_stage["forge_pr_create_allowed"])
            self.assertFalse(pub_stage["agent_merge_allowed"])
            self.assertTrue(pub_stage["human_merge_allowed"])

            self.assertTrue(receipt_path.is_file())
            mode = stat.S_IMODE(receipt_path.stat().st_mode)
            self.assertEqual(mode, 0o600)
            saved = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["schema"], "engineer.synthetic-gate-demo/v1")

    def test_cli_demo_and_rejects_non_private_receipt_parent(self):
        gates = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            open_dir = Path(tmp) / "open"
            open_dir.mkdir(mode=0o755)
            open_dir.chmod(0o755)
            bad_receipt = open_dir / "receipt.json"

            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = gates.main(["demo", "--receipt", str(bad_receipt)])
            self.assertEqual(code, 1)
            self.assertIn("private", err.getvalue().lower())


if __name__ == "__main__":
    unittest.main()
