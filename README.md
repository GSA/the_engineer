# Engineer

Engineer sets up a private AI engineering workstation on your Ubuntu computer
(WSL on Windows, or an AWS WorkSpace). It gives you two AI coding assistants
that use GSA's **USAi** models, plus the tools that keep their work
organized and reviewed:

| Tool | What it does for you |
| --- | --- |
| **Pi** | AI coding assistant in your terminal, using USAi |
| **GitHub Copilot CLI** (optional) | Copilot's terminal assistant, also using USAi; no Copilot license needed |
| **Forge** (developer tools) | Web dashboard: start an AI "workspace" for a task and watch it work |
| **Kata** (developer tools) | Task list the AI and you share |
| **roborev** (developer tools) | A second AI model reviews every change before you see it |
| **AgentsView** | History and usage of every AI session |
| **Superpowers** | Built-in skills that make the AI plan, test and verify, not just type |

Everything runs on your own computer and is reachable only from it
(`127.0.0.1`). Your USAi key stays in one private file and is never shown,
logged or put in Git. It is not placed in any environment variable, so agent
shell commands do not inherit it.

**New to terminals and on Windows?** [Pocket Engineer](https://github.com/GSA/pocket-engineer)
is a separate, lighter product: a one-double-click Windows installer for Pi and
Copilot on USAi. It has its own setup and does not use this repository. Do not install both on one machine (its installer asks you to
uninstall `~/engineer` first).

## What you need

- Ubuntu 24.04 or newer (WSL2 on Windows, or an AWS WorkSpace), with `sudo`
- A **USAi API key**
- A **GitHub account** (to open pull requests)
- About 20 minutes and 10 GB of disk space for the first install

## Install

Open an Ubuntu terminal and run:

```sh
git clone https://github.com/GSA/the_engineer.git ~/engineer
cd ~/engineer
./engineer install
```

The installer explains each step and asks before it changes anything:

1. **Ubuntu packages.** It lists the packages it needs and installs them with
   `sudo`, so it may ask for your Ubuntu password. On WSL it can also turn on
   systemd. If it does, it asks you to run `wsl --shutdown` in PowerShell,
   reopen Ubuntu, and run `./engineer install` again.
2. **Copilot.** It asks whether to set up GitHub Copilot CLI on USAi as well
   (Pi is always set up). If you already use GitHub Copilot with your own
   license, you can keep the plain `copilot` command as it is and use
   `./engineer copilot` for USAi.
3. **Developer tools.** It asks whether to install the developer tools
   (Forge, Kata and roborev). If you only want an AI assistant, answer no:
   you still get Pi and AgentsView, which shows your AI usage. Add them later
   with `./engineer install --dev-tools yes`.
4. **Build.** It builds and starts the services: all four with the developer
   tools (10–20 minutes the first time), otherwise only AgentsView.
5. **Your USAi key.** It asks for the key at a hidden prompt and checks it
   with USAi before saving it.
6. **GitHub.** It shows a code and a link for signing in to GitHub (optional
   without the developer tools).
7. **Check.** It runs `./engineer doctor` and prints the dashboard links.

Open a new terminal afterwards so the `engineer` command works from any folder.
If something stops the install, fix what the message says and run
`./engineer install` again. It picks up where it left off and remembers your
answers; `--copilot yes|no` and `--dev-tools yes|no` change them.

## Everyday use

```sh
./engineer pi          # start Pi (USAi)
./engineer copilot     # start Copilot CLI (USAi), if you set it up
./engineer status      # are the services running? (also prints the dashboard links)
./engineer start       # start the services (they also start when you log in)
./engineer stop        # stop them; nothing is lost
./engineer doctor      # check everything; every problem comes with the command that fixes it
./engineer install --dev-tools yes   # add Forge, Kata and roborev later (`no` removes their services)
```

Dashboards (open them in your browser; without the developer tools only
AgentsView runs):

| Dashboard | Link |
| --- | --- |
| Forge (workspaces) | http://127.0.0.1:18091/ |
| Kata (tasks) | http://127.0.0.1:17777/kata |
| roborev (reviews) | http://127.0.0.1:17374/reviews |
| AgentsView (history) | http://127.0.0.1:18080/ |

### Work on a repository

This needs the developer tools. Set up each Git repository you want the AI to
work in once:

```sh
./engineer add-repo ~/path/to/your-repo
```

This connects the repository to Forge, Kata and roborev. It also adds a guard
that stops anyone, human or AI, from pushing straight to `main`. The command
creates `.kata.toml` and `.roborev.toml` in the repository: commit them through
a pull request.

Then, in Forge, open the repository, create a task, and click
**Pi (USAi)** to start a workspace. The AI works on its own branch, its changes
are reviewed by roborev, and it opens a pull request for you to review. **Only
a person merges.**

## Update your USAi API key

```sh
cd ~/engineer && ./engineer key
```

Paste the new key at the hidden prompt. Engineer checks it with USAi before
saving it; if USAi rejects it, nothing is saved. Then close and reopen any Pi
or Copilot windows that were already open.

## Your USAi key and models

```sh
./engineer key       # add or replace your key (for example when it expires)
./engineer models    # pick the coding and review models from a numbered list
```

- The key is stored only in `.local/environment/secrets/usai-api-key`, readable
  only by you. Never paste it into a chat, a file in Git, or a command. Agents
  run as you, so they could read that file if told to; treat prompts and
  untrusted content accordingly.
- The defaults are `claude-sonnet-5.5` for coding and
  `gpt-6.1-sol-latest-guardrails-defaultv2` for review. Coding and review use
  different model families on purpose, so one model checks the other's work.
  Copilot works only with Claude models on USAi, so its menu lists only those.

## Update and uninstall

```sh
./engineer update                # get the latest Engineer and rebuild; your data is kept
./engineer uninstall             # remove services, commands and shell settings; keeps your data
./engineer uninstall --purge     # also delete tasks, reviews, sessions and settings
```

Uninstall removes only what `./engineer install` added. Ubuntu packages,
your own Pi or Copilot settings (`~/.pi`, `~/.copilot`), your repositories and
their committed files are left alone. After uninstalling you can delete the
`~/engineer` folder.

## What the AI can and cannot do here

Engineer is a good place to learn what AI coding assistants are good at and
where they need you.

- **They are good at:** reading unfamiliar code, explaining it, writing first
  drafts, writing and running tests, and following a plan step by step. Ask
  Pi to "brainstorm" before building something. Superpowers makes it ask
  questions, propose options and write a plan first.
- **They need you for:** deciding what to build and why, judging whether a
  change is right for users, approving anything risky, and merging. Treat every
  answer as a draft from a fast, confident junior colleague: check it.
- **Built-in guard rails:** a second model reviews each change (roborev),
  agents cannot push to `main` or merge, every session is recorded in
  AgentsView, and your key is read from its private file only when a model
  request needs it (never from an environment variable).
- **Limits:** models can be wrong while sounding sure, they forget earlier
  details in very long sessions, and they only know what is in the repository,
  the task and what you tell them. Keep tasks small and specific.

## Getting help

Behind a TLS-inspecting corporate proxy, install its CA into the system store;
see [advanced.md](docs/advanced.md#tls-inspecting-corporate-proxies).

Run `./engineer doctor` first: it names each problem and the command that
fixes it. Running `./engineer install` again is always safe. For anything
else, ask in your team channel, and include the `doctor` output, which never
contains your key.

## More detail

- [docs/advanced.md](docs/advanced.md): the lower-level commands
  `./engineer` uses, optional Librarian business context (owner-only today),
  Jira intake, demos and maintenance.
- [dist/README.md](dist/README.md): installer internals, receipts and
  fresh-host acceptance testing.
- [docs/try-in-a-second-wsl-distro.md](docs/try-in-a-second-wsl-distro.md):
  test Engineer in a separate WSL distro.
- `context/`: reference notes for AI agents working on this repository.
