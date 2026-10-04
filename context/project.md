# Objective and decisions

Build a local-first Linux agentic engineering environment inspired by
https://wesmckinney.com/blog/agentic-engineering-aug-2026/.
Prioritize roborev, Superpowers, Kenn Forge, task tracking, and AgentsView.

Confirmed with the user on 2026-10-03:

- Linux is the target. Exclude Ghosthub and all macOS-only tools.
- Begin locally; later cloud deployment is private and for the owner's use,
  not a customer-facing service. Assume access through Tailscale or a private
  VPC, not the public internet. Default listeners to loopback until a private
  network and authentication configuration is explicitly agreed.
- Use a parent integration repository and exact-commit Git submodules.
  Keep our scripts and non-secret configuration separate from upstream source.
- Pi is the likely agent, not yet a final choice.
- A user-supplied LiteLLM endpoint will be the model interface. The URL, model
  names, API protocol, and safely injected credentials are not yet supplied.
- Evaluate Kata before deciding whether a simpler database-backed task tracker
  is sufficient.
- Ask questions early rather than assuming. Favor simple code, correctness,
  maintainability, and a useful end product over prose or speed.

Added on 2026-10-04:

- Use a simple root `TODO.md` for the current backlog while task-tracker
  integration is unresolved.
- Investigate agent sandboxing as a longer-term goal. No sandbox technology or
  policy has been selected. Isolating configuration and data for smoke tests
  is not an operating-system sandbox.

# Reproducibility

`./scripts/bootstrap-sources.sh` restores the submodule revisions recorded in
the parent Git index. After the initial commit is published, a fresh
`git clone --recurse-submodules <repository-url>` also restores those revisions.
The script does not install dependencies, configure agents, or start services.

Never use `git submodule update --remote` in bootstrap or deployment. Upgrades
must explicitly change gitlinks; commit `.gitmodules` changes with their
gitlinks. Preserve upstream histories and licenses.

Pin build/runtime dependencies as they are introduced. Track non-secret
configuration templates and scripts; do not depend on undocumented manual
edits or existing home-directory configuration. Setup must be safe to rerun,
preserve data, and report failures.

`.local/` holds ignored workspace-local tools, runtime state, and diagnostic
logs. `.env` files are ignored except secret-free `.env.example` templates.
Submodules have their own ignore rules. Check staged content; ignore rules
alone do not prevent credential leaks.

# Handoff protocol

Keep `status.md` current with completed work, exact reproduction commands,
observed results, remaining blockers, and whether any owned processes remain.
Record durable tool details in `tools.md`. Do not rely on chat history or
agent-private memory. Distinguish a proposal from a decision and a startup
check from working model-backed integration.
