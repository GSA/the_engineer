# Migrating an original install to `engineer-*` names

Installs made before `./engineer` existed use the legacy unit prefix
(`kenn-kopy-*.service`), were set up with `dist/install.sh` and have no
`.local/engineer-install.json` record. They keep working as they are. This
runbook moves one of them to the current names. **Run it only after the owner
approves the downtime.** It stops every service and every running agent.

Placeholders: `OLD` is the current checkout (for example `~/kenn-kopy`), `NEW`
is the target checkout (`~/engineer`), and `P` is the legacy prefix (`kenn-kopy`).

## 0. Inventory (read-only, no downtime)

```sh
cd OLD
python3 scripts/local_env.py accept --repo OLD        # record the baseline: every PASS/FAIL line
systemctl --user list-unit-files 'P-*.service'
ls -l ~/.local/bin/kata ~/.local/bin/roborev ~/.roborev
grep -rl "OLD" ~/.pi/agent ~/.copilot ~/.kata 2>/dev/null   # global configs that name the old path
grep -l "OLD" OLD/.pi/mcp.json OLD/.github/mcp.json              # ignored project MCP configs
git -C OLD worktree list                                     # Forge worktrees live under OLD/.local
for r in $(python3 scripts/local_env.py status | python3 -c 'import json,sys;[print(p["local_path"]) for p in json.load(sys.stdin)["projects"] or []]'); do
  grep -l "OLD" "$r/.git/hooks/"* 2>/dev/null                # roborev hooks embed the roborev path
done
```

Keep this output. It is the rollback checklist.

## 1. Stop and back up

1. Finish or park open Forge workspaces and roborev jobs.
2. `systemctl --user stop P-forge.service P-roborev.service P-agentsview.service P-kata.service`
3. Back up the private state with the owner's backup tool (outside this repository), or run
   `tar --zstd -cf ~/engineer-migration-backup.tar.zst -C OLD .local/environment`.
   The archive contains the USAi key and GitHub token, so keep it private.

## 2. Move and rename

```sh
mv OLD NEW
cd NEW
python3 - <<'PY'
import json, pathlib
p = pathlib.Path(".local/environment/environment.json")
c = json.loads(p.read_text())
c = {k: (v.replace("OLD_ABSOLUTE", "NEW_ABSOLUTE") if isinstance(v, str) else v) for k, v in c.items()}
c["unit_prefix"] = "engineer"
p.write_text(json.dumps(c, indent=2) + "\n")
PY
```

Then rewrite `OLD_ABSOLUTE` to `NEW_ABSOLUTE` in the live configuration:
`.local/environment/{forge,roborev}/config.toml`, `agentsview/config.toml`,
`agentsview-tracking.json`, `roborev-service.json` (also its unit name),
`pi/{mcp,settings,trust}.json`, `pi/extensions/kata.js`, and the ignored
project MCP configs `.pi/mcp.json` and `.github/mcp.json`. In
`forge/config.toml` also change the tmux label `P-local` to `engineer-local`.
Leave logs, `tmp/`, `pi/missions/` and other history as they are
(`grep -rlI OLD_ABSOLUTE .local/environment` lists every candidate).

The databases also store the checkout path. With the services stopped, back
them up (`sqlite3` `.backup` or Python `Connection.backup`) and replace
`OLD_ABSOLUTE` with `NEW_ABSOLUTE` in:

- `forge/forge.db`: `forge_projects.local_path`, `forge_project_worktrees.path`,
  `forge_workspaces.worktree_path`, `forge_mr_worktree_links.worktree_key` and
  `.worktree_path`, `forge_worktree_stats.path`;
- `kata/kata.db`: `project_aliases.alias_identity` (`local://OLD_ABSOLUTE`);
- `roborev/reviews.db`: `repos.root_path` and `repos.identity`.

Forge has no API to change a project's path. AgentsView keys sessions by ID
and updates `file_path` on its next sync, so leave `sessions.db` alone.

Repair worktrees. Run `git worktree repair` inside each moved worktree that
belongs to another repository (`find .local -name .git -type f`), and
`git worktree repair PATH…` in `NEW` for its own worktrees. Worktrees of Forge
clones (`.local/environment/forge/clones/`) moved with their clone: rewrite
the `gitdir:` line in the worktree's `.git` file to `NEW_ABSOLUTE`, then run
`git worktree repair` in it. Worktrees whose source repository no longer
exists stay broken; that does not come from the move.

## 3. Reinstall units, links and hooks

```sh
for n in kata agentsview roborev forge; do systemctl --user disable P-$n.service; done
rm -f ~/.config/systemd/user/P-*.service
ln -sfn NEW/kata/kata ~/.local/bin/kata
ln -sfn NEW/roborev/bin/roborev ~/.local/bin/roborev
ln -sfn NEW/.local/environment/roborev ~/.roborev
for n in kata agentsview roborev forge; do python3 scripts/local_env.py install-$n-service; done
```

If `~/.pi/agent/models.json` or `~/.pi/agent/trust.json` names `OLD_ABSOLUTE`
(the global Pi provider's `usai-key.py` command and workspace trust), back them
up and rewrite the path. If `install-roborev-service` reports
`Permission denied: '/proc/PID/exe'` right after the unit starts, run it again.

For each registered repository, run `python3 scripts/local_env.py init-repo REPO`
again. It rewrites the roborev hooks to the new path and keeps `.kata.toml`,
`.roborev.toml` and history.

## 4. Verify

- `python3 scripts/local_env.py accept --repo NEW [--repo …]` matches the baseline.
- Open a Forge workspace on a Kata task, let Pi make a commit and check that
  roborev reviews it. `python3 scripts/local_env.py verify-handoff WORKSPACE_ID`
  passes.
- Reboot (or `wsl --shutdown`), log in, and run `accept` again to prove the
  services come back on their own.

## Rollback

```sh
for n in kata agentsview roborev forge; do systemctl --user disable --now engineer-$n.service; done
rm -f ~/.config/systemd/user/engineer-*.service
mv NEW OLD && cd OLD
tar --zstd -xf ~/engineer-migration-backup.tar.zst -C OLD     # restores the old environment.json, configs and databases
ln -sfn OLD/kata/kata ~/.local/bin/kata
ln -sfn OLD/roborev/bin/roborev ~/.local/bin/roborev
ln -sfn OLD/.local/environment/roborev ~/.roborev
for n in kata agentsview roborev forge; do python3 scripts/local_env.py install-$n-service; done
```

The restored `environment.json` has no `unit_prefix`, so `install-*-service`
recreates, links and starts the original `P-*.service` units. Run `init-repo`
for each repository and `git worktree repair`, restore the backed-up
`~/.pi/agent/{models,trust}.json` and project MCP configs, then confirm that `accept`
matches the baseline.

After migration the checkout still has no `.local/engineer-install.json`, so
`./engineer install` and `./engineer uninstall` continue to refuse it. Keep
managing it with `scripts/local_env.py` as before.
