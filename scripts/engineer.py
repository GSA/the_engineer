"""Engineer: one command to install, run, update and remove the local AI engineering workstation.

Run ./engineer with no arguments for the list of commands.
"""

import argparse
import getpass
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.error

import copilot_env
import host_setup
import local_env

ROOT = local_env.ROOT
HOME = Path.home()
LOCAL = local_env.RUNTIME_ROOT / ".local"
MANIFEST_SCHEMA = "engineer.install-manifest/v1"
SERVICES = ("kata", "agentsview", "roborev", "forge")
# Without the developer tools (Forge, Kata, roborev) only the AgentsView usage dashboard runs.
BASIC_SERVICES = ("agentsview",)
ADD_DEV_TOOLS = "./engineer install --dev-tools yes"
USAI_BASE_URL = "https://api.gsa.usai.gov/api/v1"
DEFAULT_CODER = "claude-sonnet-5.5"
DEFAULT_REVIEWER = "gpt-6.1-sol-latest-guardrails-defaultv2"
PURGE_PHRASE = "delete my data"
run = subprocess.run

DOCTOR_ADVICE = (
    ("usai-key", "Add your USAi key: ./engineer key"),
    ("usai-provider", "Choose your USAi models: ./engineer models"),
    ("github-login", "Sign in to GitHub: ./engineer login"),
    ("service:", "Start the services: ./engineer start (then ./engineer status)"),
    ("mcp", "Start the services, then check again: ./engineer start && ./engineer doctor"),
    ("repo:", "Set up that repository again: ./engineer add-repo PATH"),
)


def manifest_path():
    return LOCAL / "engineer-install.json"


def load_manifest():
    try:
        return json.loads(local_env.private_read(manifest_path()))
    except FileNotFoundError:
        return None


def save_manifest(record):
    local_env.private_dir(LOCAL)
    local_env.json_write(manifest_path(), {**record, "schema": MANIFEST_SCHEMA}, replace=True)


def chosen_services(choices):
    return SERVICES if choices.get("dev_tools", True) else BASIC_SERVICES


def dev_tools_chosen(record=None):
    record = load_active_manifest() if record is None else record
    return (record or {}).get("choices", {}).get("dev_tools", True)


def unit_names(services):
    return [f"{local_env.UNIT_PREFIX}-{name}.service" for name in services]


def units():
    record = load_active_manifest() or {}
    return record.get("units") or unit_names(chosen_services(record.get("choices", {})))


def child_env():
    return host_setup.tool_env(HOME)


def make_ask(assume_yes):
    def ask(question, default):
        hint = "[Y/n]" if default else "[y/N]"
        if assume_yes or not sys.stdin.isatty():
            print(f"{question} {hint} -> {'yes' if default else 'no'} (default)")
            return default
        while True:
            answer = input(f"{question} {hint} ").strip().lower()
            if not answer:
                return default
            if answer in ("y", "yes"):
                return True
            if answer in ("n", "no"):
                return False
            print("Please answer y or n.")
    return ask


def load_active_manifest():
    record = load_manifest()
    return None if record is None or record.get("uninstalled") else record


def check_install_owner():
    if (local_env.STATE / "environment.json").exists() and load_manifest() is None:
        raise RuntimeError(
            "this folder was set up with the older scripts (dist/install.sh), so ./engineer will "
            "not change it. Keep using those scripts here, or clone Engineer into a new folder.")


def install_choices(ask, *, saved, copilot_flag, dev_tools_flag=None):
    choices = {}
    if copilot_flag is not None:
        choices["copilot"] = copilot_flag == "yes"
    elif "copilot" in saved:
        choices["copilot"] = saved["copilot"]
    else:
        choices["copilot"] = ask("Also set up GitHub Copilot CLI to use USAi? (Pi is always set up)", True)
    if not choices["copilot"]:
        choices["copilot_command"] = False
    elif "copilot_command" in saved:
        choices["copilot_command"] = saved["copilot_command"]
    else:
        has_own = (HOME / ".copilot").exists()
        choices["copilot_command"] = ask(
            "You already use GitHub Copilot. Should the plain `copilot` command use USAi instead? "
            "(No keeps your GitHub Copilot as is; `./engineer copilot` always uses USAi)" if has_own else
            "Should the plain `copilot` command use USAi? (`./engineer copilot` always does)",
            not has_own)
    if dev_tools_flag is not None:
        choices["dev_tools"] = dev_tools_flag == "yes"
    elif "dev_tools" in saved:
        choices["dev_tools"] = saved["dev_tools"]
    else:
        choices["dev_tools"] = ask(
            "Also install the developer tools (Forge workspaces, Kata tasks, roborev reviews)? "
            "Most people who only want an AI assistant can say no.", True)
    if "pi_command" in saved:
        choices["pi_command"] = saved["pi_command"]
    else:
        choices["pi_command"] = ask("Should the plain `pi` command open Engineer's Pi (USAi)?",
                                    not (HOME / ".pi").exists())
    return choices


def owns_unit(unit):
    """True when the user manager loads ``unit`` from this install's systemd directory."""
    result = run(["systemctl", "--user", "show", unit, "--property=FragmentPath", "--value"],
                 capture_output=True, text=True)
    fragment = (result.stdout or "").strip()
    return bool(fragment) and Path(fragment).parent == local_env.STATE / "systemd"


def repo_paths(record=None):
    record = load_active_manifest() if record is None else record
    return [entry["path"] if isinstance(entry, dict) else entry for entry in (record or {}).get("repos", [])]


def owned_units():
    """This install's units, skipping any the user manager loads from another checkout."""
    return [unit for unit in units() if owns_unit(unit) or not unit_exists(unit)]


def unit_exists(unit):
    result = run(["systemctl", "--user", "show", unit, "--property=LoadState", "--value"],
                 capture_output=True, text=True)
    return (result.stdout or "").strip() not in ("", "not-found")


def disable_units(names):
    """Disable and unlink the units this install owns; others' units are left alone."""
    for unit in names:
        if not owns_unit(unit):
            continue
        run(["systemctl", "--user", "disable", "--now", unit])
        linked = HOME / ".config/systemd/user" / unit
        if linked.is_symlink() and Path(os.readlink(linked)).parent == local_env.STATE / "systemd":
            linked.unlink()
    if names:
        run(["systemctl", "--user", "daemon-reload"])


def stop_services(quiet=False):
    for unit in reversed(owned_units()):
        run(["systemctl", "--user", "stop", unit], capture_output=quiet)


def restart_agents():
    """Forge and roborev start agents with the key and models; reload them if they run."""
    for unit in owned_units():
        if "-forge." in unit or "-roborev." in unit:
            run(["systemctl", "--user", "try-restart", unit])


def install(args):
    ask = make_ask(args.yes)
    check_install_owner()
    record = load_manifest() or {"units": [], "repos": []}
    if record.pop("uninstalled", False):
        # Reinstalling over data kept by an earlier uninstall: start a fresh record of what is created.
        record = {"units": [], "repos": [], "choices": record.get("choices", {})}
    record.setdefault("kata_config_existed", (HOME / ".kata/config.toml").exists())
    choices = install_choices(ask, saved=record.get("choices", {}), copilot_flag=args.copilot,
                              dev_tools_flag=args.dev_tools)
    record["choices"] = choices
    save_manifest(record)
    services = chosen_services(choices)
    print("\nStep 1 of 4: preparing Ubuntu (packages, Node.js, Pi"
          + (", Copilot CLI" if choices["copilot"] else "") + ")...")
    try:
        host_setup.prepare(ask, want_copilot=choices["copilot"], record=record,
                           pi_version=local_env.PI_VERSION, home=HOME)
    finally:
        save_manifest(record)
    print("\nStep 2 of 4: building and starting "
          + ("Forge, Kata, roborev and AgentsView" if choices["dev_tools"] else "the AgentsView usage dashboard")
          + " (the first run takes " + ("10-20" if choices["dev_tools"] else "a few") + " minutes)...")
    if record.get("units"):
        stop_services(quiet=True)
        # Developer tools dropped since the last install: switch their services off; data is kept.
        disable_units([unit for unit in record["units"] if unit not in unit_names(services)])
    # Record the units before building, so a retry or uninstall after a partial failure
    # can stop the services that did start. Uninstall checks each unit's owner first.
    record["units"] = unit_names(services)
    save_manifest(record)
    command = [sys.executable, str(ROOT / "dist/install.py"), "--services", "user", "--guided"]
    if not choices["dev_tools"]:
        command.append("--without-dev-tools")
    if not (local_env.STATE / "usai.json").exists():
        command += ["--usai-base-url", USAI_BASE_URL, "--usai-model", DEFAULT_CODER,
                    "--usai-review-model", DEFAULT_REVIEWER]
    if run(command, cwd=ROOT, env=child_env()).returncode != 0:
        raise RuntimeError("the build or service setup stopped; read the message above, fix it, "
                           "then run ./engineer install again (it picks up where it left off)")
    if choices["copilot"]:
        copilot_env.configure_copilot()
    host_setup.write_shell_block(host_setup.shell_block(
        ROOT, pi=choices["pi_command"], copilot=choices["copilot_command"]), HOME)
    print("\nStep 3 of 4: your USAi key and GitHub sign-in...")
    interactive = sys.stdin.isatty() and not args.yes
    if not (local_env.STATE / "secrets/usai-api-key").exists():
        if interactive:
            save_key(ask)
            restart_agents()
        else:
            print("Skipped: run ./engineer key in a terminal to add your USAi key.")
    if not github_signed_in():
        if interactive and ask("Sign in to GitHub now? (needed for pull requests"
                               + ("" if choices["dev_tools"] else "; optional") + ")", choices["dev_tools"]):
            login()
        else:
            print("Skipped: run ./engineer login to sign in to GitHub.")
    print("\nStep 4 of 4: checking everything...")
    healthy = doctor()
    print("\nOpen a new terminal (or run: source ~/.bashrc) so the `engineer` command works everywhere.")
    print("Dashboards: " + dashboards())
    if healthy:
        print("Engineer is ready. Try: ./engineer pi" + ("   or   ./engineer copilot" if choices["copilot"] else ""))
    return healthy


def github_signed_in():
    try:
        hosts = local_env.private_read(local_env.STATE / "gh/hosts.yml")
    except (FileNotFoundError, RuntimeError):
        return False
    return any(line.rstrip() == "github.com:" for line in hosts.splitlines())


def login():
    print("A GitHub sign-in code appears below; open the link it shows and enter that code.")
    result = run([sys.executable, str(ROOT / "scripts/gh-local.py"), "auth", "login", "--hostname",
                  "github.com", "--web", "--git-protocol", "https", "--insecure-storage"], env=child_env())
    if result.returncode != 0:
        raise RuntimeError("GitHub sign-in did not finish; run ./engineer login to try again")
    restart_agents()
    print("Signed in to GitHub. Engineer keeps this sign-in separate from your own GitHub CLI.")


def require_installed():
    try:
        return local_env.settings()
    except FileNotFoundError:
        raise RuntimeError("Engineer is not installed in this folder yet; run ./engineer install") from None


def save_key(ask):
    if not sys.stdin.isatty():
        raise RuntimeError("run ./engineer key in a terminal; a key is never accepted as an argument or pipe")
    require_installed()
    print("Paste your USAi API key. It stays hidden while you type and is never shown again.")
    key = local_env.validate_key(getpass.getpass("USAi API key: "))
    base_url = copilot_env.usai_base_url()
    models = None
    try:
        models = local_env.fetch_usai_models(base_url, key)
    except RuntimeError as error:
        if "HTTP 401" in str(error) or "HTTP 403" in str(error):
            raise RuntimeError("USAi rejected this key. Check that you copied all of it (or create a "
                               "new one), then run ./engineer key again. Nothing was saved.") from None
        raise RuntimeError(f"USAi could not check the key ({error}). Nothing was saved.") from None
    except (urllib.error.URLError, OSError, TimeoutError):
        print("Could not reach USAi to check the key (are you on the network or VPN?).")
        if not ask("Save the key anyway and check it later?", False):
            raise RuntimeError("Nothing was saved. Connect to the network, then run ./engineer key again.") from None
    local_env.private_dir(local_env.STATE / "secrets")
    local_env.private_write(local_env.STATE / "secrets/usai-api-key", key + "\n", replace=True)
    if models:
        local_env.save_usai_catalog(base_url, models)
        print(f"USAi accepted the key ({len(models)} models available). It is saved privately and was not displayed.")
    else:
        print("Key saved privately; it was not displayed. Run ./engineer doctor once you are online.")


def key_command(args):
    save_key(make_ask(False))
    restart_agents()
    print("Close and reopen any Pi or Copilot sessions that were already open so they use the new key.")


def chat_models(catalog):
    return sorted(model for model in set(catalog) if model not in local_env.USAI_EMBEDDING_MODELS
                  and local_env.usai_model_family(model) in local_env.ADVERSARIAL_MODEL_FAMILIES)


def reviewer_models(catalog, coder):
    family = local_env.usai_model_family(coder)
    return [model for model in chat_models(catalog) if local_env.usai_model_family(model) != family]


def copilot_models(catalog):
    return [model for model in chat_models(catalog)
            if local_env.usai_model_family(model) in copilot_env.SUPPORTED_FAMILIES]


def choose(title, options, current, reply=input):
    if not options:
        raise RuntimeError(f"USAi offers no models for: {title}")
    current = current if current in options else options[0]
    print(f"\n{title}")
    for number, option in enumerate(options, 1):
        print(f"  {number:>2}. {option}{'   (current)' if option == current else ''}")
    while True:
        answer = reply(f"Press Enter to keep {current}, or type a number or name: ").strip()
        if not answer:
            return current
        if answer.isdigit() and 1 <= int(answer) <= len(options):
            return options[int(answer) - 1]
        if answer in options:
            return answer
        print("That is not one of the listed models.")


def models_command(args):
    require_installed()
    base_url = copilot_env.usai_base_url()
    try:
        catalog = local_env.fetch_usai_models(base_url, local_env.load_usai_key())
        local_env.save_usai_catalog(base_url, catalog)
    except FileNotFoundError:
        raise RuntimeError("add your USAi key first: ./engineer key") from None
    except (RuntimeError, urllib.error.URLError, OSError, TimeoutError) as error:
        print(f"Could not refresh the model list from USAi ({error}); using the last saved list.")
        saved = local_env.STATE / "usai-models.json"
        catalog = (json.loads(local_env.private_read(saved))["models"] if saved.exists()
                   else list(local_env.USAI_CHAT_MODELS))
    current = json.loads(local_env.private_read(local_env.STATE / "usai.json"))
    coder = choose("Coding model (Pi and Forge workspaces):", chat_models(catalog), current.get("model"))
    reviewer = choose("Review model (roborev; a different model family checks the coder's work):",
                      reviewer_models(catalog, coder), current.get("review_model"))
    api = json.loads(local_env.private_read(local_env.STATE / "pi/models.json"))["providers"]["usai"]["api"]
    local_env.configure_provider(base_url, coder, api, review_model=reviewer)
    if copilot_env.copilot_home().exists():
        copilot = choose("Copilot model (only Claude models work with Copilot on USAi):",
                         copilot_models(catalog), current.get("copilot_model"))
        copilot_env.configure_copilot(copilot)
    restart_agents()
    print("Saved. New Pi, Copilot and Forge sessions use these models.")


def doctor(args=None):
    if not (local_env.STATE / "environment.json").exists():
        print("Engineer is not installed in this folder yet. Run: ./engineer install")
        return False
    failures = local_env.accept(home=HOME, repos=repo_paths())
    status, message = copilot_env.check()
    print(f"{status} copilot: {message}")
    if status == "FAIL":
        failures.append("copilot")
    if not dev_tools_chosen():
        print(f"Developer tools are not installed (optional). To add them: {ADD_DEV_TOOLS}")
    if not failures:
        print("\nEverything checks out.")
        return True
    print("\nWhat to do next:")
    if load_manifest() is None:
        print("  - This folder was set up with the older scripts; follow the FAIL lines above "
              "(dist/README.md explains each command).")
        return False
    shown = set()
    for failure in failures:
        advice = next((text for prefix, text in DOCTOR_ADVICE if failure.startswith(prefix)),
                      "Repair the installation (safe to rerun): ./engineer install")
        if advice not in shown:
            shown.add(advice)
            print(f"  - {advice}")
    return False


def dashboards():
    if not dev_tools_chosen():
        return f"AgentsView (your AI usage) http://127.0.0.1:{local_env.AGENTSVIEW_PORT}/"
    return (f"Forge http://127.0.0.1:{local_env.FORGE_PORT}/ | Kata {local_env.KATA_URL}/kata | "
            f"roborev http://127.0.0.1:{local_env.ROBOREV_WEB_PORT}/reviews | "
            f"AgentsView http://127.0.0.1:{local_env.AGENTSVIEW_PORT}/")


def start(args):
    require_installed()
    for unit in owned_units():
        run(["systemctl", "--user", "start", unit])
    status(args)


def stop(args):
    require_installed()
    stop_services()
    print("Stopped. Your tasks, reviews and settings are kept; ./engineer start brings them back.")


def status(args):
    require_installed()
    for unit in units():
        state = run(["systemctl", "--user", "is-active", unit], capture_output=True, text=True).stdout.strip()
        print(f"  {unit:<34} {'running' if state == 'active' else state or 'unknown'}")
    print("Dashboards: " + dashboards())


def roborev_hooked(repo):
    try:
        hook = local_env.repo_init_module().hook_path(repo, "post-commit")
        return "roborev" in hook.read_text(errors="replace")
    except (OSError, RuntimeError, subprocess.SubprocessError):
        return False


def add_repo(args):
    require_installed()
    if not dev_tools_chosen():
        raise RuntimeError("add-repo sets up Forge, Kata and roborev, which are the developer tools "
                           f"you chose not to install. To add them, run: {ADD_DEV_TOOLS}")
    repo = Path(args.path).expanduser().resolve()
    repo_init = local_env.repo_init_module()
    try:
        before = {"guard": repo_init.is_installed(repo), "hooks": roborev_hooked(repo)}
    except (OSError, RuntimeError, subprocess.SubprocessError):
        before = {"guard": True, "hooks": True}
    try:
        code = local_env.init_repo(repo)
    finally:
        record_repo(repo, before)
    if code == 0:
        print("Commit the new .kata.toml and .roborev.toml files through a pull request, not on main.")
    return code == 0


def record_repo(repo, before):
    """Record which protections exist now that did not before, even after a failed step."""
    repo_init = local_env.repo_init_module()
    try:
        after = {"guard": repo_init.is_installed(repo), "hooks": roborev_hooked(repo)}
    except (OSError, RuntimeError, subprocess.SubprocessError):
        after = {"guard": False, "hooks": False}
    record = load_active_manifest()
    if record is None:
        return
    entries = [entry for entry in record.get("repos", [])
               if (entry["path"] if isinstance(entry, dict) else entry) != str(repo)]
    previous = next((entry for entry in record.get("repos", [])
                     if isinstance(entry, dict) and entry["path"] == str(repo)), {})
    entries.append({"path": str(repo),
                    "guard_added": previous.get("guard_added", False) or (after["guard"] and not before["guard"]),
                    "hooks_added": previous.get("hooks_added", False) or (after["hooks"] and not before["hooks"])})
    record["repos"] = sorted(entries, key=lambda entry: entry["path"])
    save_manifest(record)


def pi(args):
    env = child_env()
    script = str(ROOT / "scripts/pi-local.py")
    os.execve(sys.executable, [sys.executable, script, *args.rest], env)


def copilot(args):
    command, env = copilot_env.copilot_launch(args.rest)
    os.execve(command[0], command, env)


def update(args):
    result = run(["git", "-C", str(ROOT), "pull", "--ff-only"])
    if result.returncode != 0:
        raise RuntimeError("could not download the update (local changes or no network?); "
                           "nothing was changed")
    # Run install from the freshly downloaded code, not the copy already in memory.
    argv = [sys.executable, str(ROOT / "scripts/engineer.py"), "install"]
    if args.yes:
        argv.append("--yes")
    if args.copilot:
        argv += ["--copilot", args.copilot]
    if args.dev_tools:
        argv += ["--dev-tools", args.dev_tools]
    os.execv(sys.executable, argv)


def remove_link(link, target):
    if link.is_symlink() and link.resolve() == Path(target).resolve():
        link.unlink()
        return True
    return False


def uninstall(ask, *, purge):
    record = load_manifest()
    if record is not None and record.get("uninstalled"):
        raise RuntimeError("Engineer was already removed from this computer; your kept data is in "
                           f"{local_env.STATE}. Run ./engineer install to use it again.")
    if record is None:
        raise RuntimeError("no ./engineer install record was found in this folder, so nothing was removed "
                           "(installs made with the older scripts are removed by hand; see dist/README.md)")
    print("This stops and removes Engineer's services, commands and shell settings.")
    print("Ubuntu packages stay installed. Your repositories and their committed files are not touched.")
    print(f"Your tasks, reviews and settings in {local_env.STATE} are "
          + ("DELETED." if purge else "kept."))
    if not ask("Remove Engineer from this computer?", False):
        print("Nothing was changed.")
        return
    if purge and input(f'Type "{PURGE_PHRASE}" to also delete your Engineer data: ').strip() != PURGE_PHRASE:
        raise RuntimeError("your data was not deleted, and nothing else was changed")
    disable_units(list(reversed(record.get("units", []))))
    repo_init = local_env.repo_init_module()
    for entry in record.get("repos", []):
        # Only protections this install added are removed; pre-existing ones stay.
        if not isinstance(entry, dict) or not Path(entry["path"]).is_dir():
            continue
        if entry.get("guard_added"):
            repo_init.remove_guard(Path(entry["path"]))
        if entry.get("hooks_added"):
            run([str(local_env.RUNTIME_ROOT / "roborev/bin/roborev"), "hook", "uninstall"], cwd=entry["path"])
    remove_link(HOME / ".local/bin/kata", local_env.RUNTIME_ROOT / "kata/kata")
    remove_link(HOME / ".local/bin/roborev", local_env.RUNTIME_ROOT / "roborev/bin/roborev")
    remove_link(HOME / ".roborev", local_env.STATE / "roborev")
    kata_config = HOME / ".kata/config.toml"
    if not record.get("kata_config_existed") and kata_config.is_file():
        kata_config.unlink()
        if not any((HOME / ".kata").iterdir()):
            (HOME / ".kata").rmdir()
    removed = host_setup.undo(record, HOME)
    if purge:
        shutil.rmtree(LOCAL)
    else:
        save_manifest({"uninstalled": True, "choices": record.get("choices", {})})
    print("Removed: services, kata/roborev commands" + "".join(f", {item}" for item in removed) + ".")
    if not purge:
        print(f"Kept your data in {local_env.STATE}. To delete it too: rm -rf {LOCAL}")
    print(f"You can now delete this folder ({ROOT}) if you no longer need it.")


def uninstall_command(args):
    uninstall(make_ask(False), purge=args.purge)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="engineer", description="Install, run and remove the Engineer AI workstation.",
        epilog="Your USAi key is only ever typed at a hidden prompt (./engineer key), never on the command line.")
    commands = parser.add_subparsers(dest="command", metavar="COMMAND")
    setup = commands.add_parser("install", help="install or repair everything (safe to rerun)")
    setup.add_argument("--copilot", choices=("yes", "no"), help="set up Copilot CLI on USAi without asking")
    setup.add_argument("--dev-tools", choices=("yes", "no"),
                       help="install the developer tools (Forge, Kata, roborev) without asking")
    setup.add_argument("--yes", action="store_true", help="accept the default answer to every question")
    setup.set_defaults(func=install)
    commands.add_parser("doctor", help="check the installation and say how to fix problems").set_defaults(func=doctor)
    commands.add_parser("start", help="start the services").set_defaults(func=start)
    commands.add_parser("stop", help="stop the services (data is kept)").set_defaults(func=stop)
    commands.add_parser("status", help="show whether the services are running").set_defaults(func=status)
    commands.add_parser("key", help="add or replace your USAi key (hidden prompt)").set_defaults(func=key_command)
    commands.add_parser("models", help="choose the USAi models for coding and review").set_defaults(func=models_command)
    commands.add_parser("login", help="sign in to GitHub for pull requests").set_defaults(func=lambda args: login())
    repo = commands.add_parser("add-repo", help="set up a Git repository for Forge, Kata and roborev "
                               "(developer tools)")
    repo.add_argument("path", type=Path)
    repo.set_defaults(func=add_repo)
    for name, func, text in (("pi", pi, "open Pi on USAi"), ("copilot", copilot, "open Copilot CLI on USAi")):
        launcher = commands.add_parser(name, help=text, add_help=False)
        launcher.add_argument("rest", nargs=argparse.REMAINDER)
        launcher.set_defaults(func=func)
    upgrade = commands.add_parser("update", help="download the latest Engineer and rebuild")
    upgrade.add_argument("--copilot", choices=("yes", "no"), help=argparse.SUPPRESS)
    upgrade.add_argument("--dev-tools", choices=("yes", "no"), help=argparse.SUPPRESS)
    upgrade.add_argument("--yes", action="store_true", help="accept the default answer to every question")
    upgrade.set_defaults(func=update)
    remove = commands.add_parser("uninstall", help="remove Engineer (keeps your data unless --purge)")
    remove.add_argument("--purge", action="store_true", help="also delete tasks, reviews, sessions and settings")
    remove.set_defaults(func=uninstall_command)
    return parser


def main(argv=None):
    os.umask(0o077)
    # Engineer's own Node.js, Pi and Copilot CLI come first for every step and child process.
    os.environ["PATH"] = host_setup.tool_path(HOME)
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    try:
        result = args.func(args)
    except host_setup.NeedsRestart as error:
        print(str(error), file=sys.stderr)
        return 3
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Problem: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nStopped. Nothing else was changed; rerun the command to continue.", file=sys.stderr)
        return 130
    return 1 if result is False else 0


if __name__ == "__main__":
    sys.exit(main())
