
export const PR_DESCRIPTION_GUIDANCE = [
	"Choose PR description length and structure from the meaningful changes and reviewer needs, not file or line counts.",
	"A focused fix or mechanical change can be a short paragraph, even across many files.",
	"For independent changes, use bullets or sections only when they help explain behavior, rationale, compatibility, or operational impact.",
	"There is no required paragraph, heading, or bullet count; do not pad the description or repeat the overview.",
	"Preserve actionable limitations, migration requirements, and approval gates; omit boilerplate and raw test transcripts.",
].join(" ");

export const FORGE_WORKSPACE_SECTION = [
	"Kenn Forge Workspace Execution & Completion Policy:",
	"- This session is running inside an autonomous Kenn Forge workspace.",
	"- Unless a genuine blocking requirement ambiguity cannot be resolved from the repository or Kata/issue description, do NOT stop after `brainstorming` or `writing-plans` to wait for human approval of a classification, design, written spec, implementation plan, or execution method.",
	"- Keep any working spec or implementation plan in ignored `.local/plans/` (never under `docs/superpowers/`), execute the plan directly with TDD, and remove temporary `.local/plans/` files before delivery.",
	"- Apply the coder contract's bounded roborev delivery policy: reuse evidence for unchanged reviewed code; otherwise run `roborev review --branch --wait --min-severity medium` at most once per delivery, followed by at most one focused, verified fix pass. Do not re-review merely to obtain a passing verdict. Record dispositions with `roborev respond <job>` and close a review only when all actionable findings are fixed or confirmed stale/invalid; leave valid out-of-scope findings open and ask the owner. Hand recurring or unresolved confirmed findings to the owner; pause publication and completion for unresolved task-scoped medium/high/critical defects. Low findings do not block delivery. Reloads, resumes, and skill transitions reuse the same review/fix allowance and recorded evidence.",
	"- Pi enforces the review budget: it blocks a second `roborev review --branch` (or `--since`, `roborev refine`, unscoped `roborev fix`) on this branch unless the human confirms in the Pi UI, and the count survives reloads and resumes. A fix pass addresses only the findings recorded in the first review; verify with `roborev respond <job>` dispositions plus targeted tests, or at most `roborev review <sha>` of the fix commit itself. Findings on a fix commit outside the originals are recorded for the owner, not actioned. When Pi flags a possible review loop, stop, assess whether you are in a loop and need a human, summarize open findings, and hand off by PR comment, Forge or Kata instead of continuing.",
	"- When implementation and verification are complete, do NOT stop to ask whether to merge locally to `main`, keep the branch as-is, or discard work.",
	"- Always complete the workspace by pushing the workspace branch (`git push -u origin HEAD`) and creating or updating the GitHub pull request (`gh pr create` / `gh pr edit`). This is pre-authorized: do not ask for permission.",
	"- Make every edit and commit inside this workspace worktree on its branch. If the task needs changes in another repository, create a feature branch there (never commit on its `main` checkout), push it, and open a PR there.",
	"- Never commit to, push to, or ask the human whether to push to `main` or the default branch, and never merge a PR; deliver through branches and pull requests.",
	`- ${PR_DESCRIPTION_GUIDANCE} The automatic PR formatter uses the same guidance after \`gh pr create\` / \`gh pr edit\`.`,
	"- Subagents are optional; use them only when the task benefits. In this workspace Pi launches `worker` and `delegate` subagents (and `parallel` fan-outs that include them) in managed worktrees under the Pi agent dir unless the call sets `worktree` itself; `scout`, `oracle` and `reviewer` run in place. In a `workflow: true` script, set `worktree: true` on each writing child yourself. Commit or stash first: an isolated launch refuses a dirty or untracked checkout. The result lists each child's patch and a `Worktree handoff` JSON; land each changed patch on the workspace branch with `git apply --3way <patch>`, review, test and commit it yourself. When the handoff does not report `cleanup complete` (for example after an async or failed run), remove leftovers with `git worktree remove <path>` and `git branch -D <branch>` from `git worktree list`.",
	"- Forge links the workspace branch's PR to this workspace automatically. Register PRs in other repositories or extra stacked PRs with `mcp__kenn_forge__kenn_forge_add_workspace_target`, and worked GitHub issues or Kata tasks with it or `mcp__kenn_forge__kenn_forge_add_workspace_kata_target` (using `mcp__kenn_forge__kenn_forge_list_repos` if needed to look up `platform_repo_id`), then confirm with `mcp__kenn_forge__kenn_forge_list_workspace_targets`.",
].join("\n");

export const BRAINSTORMING_OVERRIDE = [
	"",
	"## Kenn Forge Workspace Override (Active)",
	"",
	"You are running inside an autonomous Kenn Forge workspace.",
	"- Unless a genuine blocking requirement ambiguity cannot be resolved from the codebase or Kata/issue specification, `<HARD-GATE>` is satisfied by the workspace launch prompt: do **NOT** stop and wait for human approval of your design or design doc.",
	"- Do **NOT** open with questions, including why the work is wanted: the workspace launch prompt and Kata/issue description are the answers. State your calls as decisions in the design doc instead of asking.",
	"- Save any working design doc to ignored `.local/plans/` (never under `docs/superpowers/specs/` and never commit it to Git).",
	"- Run the builder check (a `subagent` with `model: \"inherit\"`, or read the doc as that builder yourself). Settle \"minor\" items yourself; bring a \"theirs\" item to the human only if it is a genuine blocking requirement ambiguity. Otherwise record it as your call.",
	"- Then immediately proceed to `writing-plans` and TDD implementation in the same turn.",
].join("\n");

export const WRITING_PLANS_OVERRIDE = [
	"",
	"## Kenn Forge Workspace Override (Active)",
	"",
	"You are running inside an autonomous Kenn Forge workspace.",
	"- Save any working implementation plan to ignored `.local/plans/` (never under `docs/superpowers/plans/` and never commit it to Git).",
	"- After self-reviewing the plan, do **NOT** stop at `Execution Handoff` to ask the human partner to review the plan or choose between Subagent-driven and Native execution.",
	"- Immediately proceed to implement the plan with TDD in this session (or using `subagent` with `model: \"inherit\"` for independent tasks), remove temporary `.local/plans/` artifacts before delivery, and apply the bounded roborev delivery policy, reusing earlier review/fix evidence without restarting the allowance. When no unresolved task-scoped medium/high/critical defects remain, push the branch, create/update the PR, and register the PR and Kata/issue targets with Forge.",
].join("\n");

export const FINISHING_BRANCH_OVERRIDE = [
	"",
	"## Kenn Forge Workspace Override (Active)",
	"",
	"You are running inside a Kenn Forge workspace. Do **NOT** present Step 4's 4-option menu or ask whether to merge locally to `main`.",
	"",
	"Once Step 1 (tests pass) is verified:",
	"1. Apply the bounded roborev delivery policy, reusing earlier review/fix evidence without restarting the allowance, and remove any temporary `.local/plans/` files. Pause publication for unresolved task-scoped medium/high/critical defects and hand them to the owner rather than repeating review/fix passes.",
	`2. Automatically execute **Option 2 (Push and Create a Pull Request)**: push the workspace branch (\`git push -u origin HEAD\`) and create or update the pull request (\`gh pr create\` / \`gh pr edit\`). ${PR_DESCRIPTION_GUIDANCE}`,
	"3. Forge links the workspace branch's PR automatically. Register PRs in other repositories, extra stacked PRs, and any worked GitHub issue or Kata task with Forge using `mcp__kenn_forge__kenn_forge_add_workspace_target` and `mcp__kenn_forge__kenn_forge_add_workspace_kata_target` (using the `Workspace ID` and `Repository` from the Kenn Forge Workspace Context), then verify with `mcp__kenn_forge__kenn_forge_list_workspace_targets`.",
	"4. Do not remove the Forge workspace worktree; Forge manages workspace worktree lifecycle.",
].join("\n");
