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

Then rewrite the remaining absolute paths that still name `OLD_ABSOLUTE` in
`.local/environment/{forge,roborev,kata}/config.toml`, `pi/mcp.json`,
`pi/settings.json` and `agentsview/config.toml` (`grep -rl OLD_ABSOLUTE .local/environment`).
Kata, Forge and roborev databases store project IDs and history, not the
checkout path. Forge worktree records do name it: run
`git worktree repair` in `NEW` and in each registered repository.

## 3. Reinstall units, links and hooks

```sh
for n in kata agentsview roborev forge; do systemctl --user disable P-$n.service; done
rm -f ~/.config/systemd/user/P-*.service
ln -sfn NEW/kata/kata ~/.local/bin/kata
ln -sfn NEW/roborev/bin/roborev ~/.local/bin/roborev
ln -sfn NEW/.local/environment/roborev ~/.roborev
for n in kata agentsview roborev forge; do python3 scripts/local_env.py install-$n-service; done
python3 scripts/local_env.py set-key        # only if a global Pi provider linked the old usai-key.py path
```

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
tar --zstd -xf ~/engineer-migration-backup.tar.zst -C OLD     # restores the old environment.json and configs
ln -sfn OLD/kata/kata ~/.local/bin/kata
ln -sfn OLD/roborev/bin/roborev ~/.local/bin/roborev
ln -sfn OLD/.local/environment/roborev ~/.roborev
for n in kata agentsview roborev forge; do python3 scripts/local_env.py install-$n-service; done
```

The restored `environment.json` has no `unit_prefix`, so `install-*-service`
recreates, links and starts the original `P-*.service` units. Run `init-repo`
for each repository and `git worktree repair`, then confirm that `accept`
matches the baseline.

After migration the checkout still has no `.local/engineer-install.json`, so
`./engineer install` and `./engineer uninstall` continue to refuse it. Keep
managing it with `scripts/local_env.py` as before.
