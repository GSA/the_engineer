# Simplification and refactoring guide

## Completed simplifications

1. **Direct native CLI usage over custom Python wrappers (`sc6x`, `sb77`)**:
   - Removed `scripts/roborev-local.py`, `scripts/roborev_hooks.py`, and
     `scripts/test_roborev_hooks.py`.
   - Replaced custom Git hook wrappers and `the_librarian`'s synchronous
     `pre-commit` review gate with native `roborev init --no-daemon` hooks and
     batched post-commit reviews (`post_commit_batch_size = 5`).
   - Disabled Copilot CLI's global `agenthook.json` stop-hook loop.
2. **Affirmative, compact context documents (`sc6x`, `qc96`)**:
   - Replaced append-only session logs and negative-disclaimer blocks across
     `the_engineer`, `the_librarian`, and `the_knowitall` with concise,
     affirmative current-state documentation.
   - Removed superseded `context/kata-adoption.md` and
     `context/kata-evaluation.md`.
3. **USAi `pi-subagents` inheritance (`sb77`)**:
   - Standardized both `.local/environment/pi/settings.json` and
     `~/.pi/agent/settings.json` on `defaultProvider: "usai"` and
     `defaultModel: "inherit"`, and injected `action: "resume"` and
     `reviewer` vs. `roborev` guidance via `PI_SUBAGENT_DESCRIPTIONS`.

## Active code refactoring track (`2jgk`)

Kata `2jgk` (in worktree `.local/environment/forge/worktrees/kenn-forge/work-7d57d583`)
tracks structural modularization of `scripts/local_env.py` and `dist/install.py`:

- Keep `scripts/` wrappers limited to environment isolation that native CLIs do
  not provide on their own (`pi-local.py` for `PI_CODING_AGENT_DIR`,
  `gh-local.py` for `GH_CONFIG_DIR`, `terminal-local.py` for isolated tmux
  sockets, and `usai-key.py` for private key lookup).
- Prefer declarative templates or small focused modules over monolithic string
  builders in `scripts/local_env.py`.
- Reconcile `dist/install.py` with the four-unit user systemd deployment model
  (`t14m`).
