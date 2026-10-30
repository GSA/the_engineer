# WSL2 rehearsal instance (Layer 2, deferred)

Kata `the_engineer#t592` is deferred until after the MVP. This guide records
the Layer 2 design: a second WSL2 Ubuntu 24.04 distro, `engineer-mvp`, on the
same Windows host, with its own files, users, and services. Layer 1, an isolated
Librarian MVP instance, is described in the
[README](../README.md#isolated-librarian-mvp-instance-layer-1).

Use WSL distros rather than containers. Containers would break
`systemd --user` units, Forge worktree paths, and Librarian's absolute index
paths (`the_librarian` Decision 0004).

## Ports are shared with your primary distro

All WSL2 distros run in one VM and share one network namespace
([Microsoft: What is WSL](https://learn.microsoft.com/windows/wsl/about)).
`127.0.0.1` in `engineer-mvp` is the same `127.0.0.1` as in your primary distro.
The default ports would collide, or silently reach your primary services.

Set `KENN_KOPY_PORT_OFFSET=1000` in `engineer-mvp` before `setup` or
`dist/install.sh`. `setup` saves it in `environment.json`, so services and later
commands use it. A different value later is an error. The offset must be a
non-negative integer that does not overlap the default ports.

| Service | Primary distro | `engineer-mvp` (offset 1000) |
| --- | --- | --- |
| Forge (MCP) | 18091 (18092) | 19091 (19092) |
| Kata | 17777 | 18777 |
| roborev API, UI | 17373, 17374 | 18373, 18374 |
| AgentsView | 18080 | 19080 |

Both stacks can run at once. Do not stop the primary services.

## Create a clean instance

This needs WSL 2.4.10 or later for Ubuntu's image format. Check with
`wsl --version`. Run in PowerShell. Keep the files under `%LOCALAPPDATA%`,
which OneDrive does not sync.

```powershell
$dir = "$env:LOCALAPPDATA\engineer-wsl"
New-Item -ItemType Directory -Force -Path $dir
wsl --install Ubuntu-24.04 --name engineer-mvp --location "$dir\engineer-mvp"
```

The first launch asks for a user name and password. Set a real password;
`sudo` needs it. Without Microsoft Store access, download the
`ubuntu-24.04.*-wsl-amd64.wsl` image and `SHA256SUMS` from
https://releases.ubuntu.com/noble/, check the hash, and use
`wsl --install --from-file <image>.wsl --name engineer-mvp --location "$dir\engineer-mvp"`.

Inside `engineer-mvp`, enable systemd and keep your user as the default after
an import:

```sh
printf '[boot]\nsystemd=true\n[user]\ndefault=%s\n' "$USER" | sudo tee /etc/wsl.conf
```

Then save the clean baseline from PowerShell. It holds only the stock image and
your account. No repos, keys, or logins.

```powershell
wsl --terminate engineer-mvp
wsl --export engineer-mvp "$dir\engineer-mvp-base.tar"
```

## Stand it up inside `engineer-mvp`

```sh
export KENN_KOPY_PORT_OFFSET=1000
export KATA_SERVER=http://127.0.0.1:18777
```

Add both lines to `~/.bashrc` in `engineer-mvp`. Then follow
[Requirements](../README.md#requirements) and [Stand it up](../README.md#stand-it-up). `KATA_SERVER` keeps the native `kata` CLI off the primary Kata. Check that
`python3 scripts/local_env.py status` shows `"port_offset": 1000`.

## Snapshots and reset

A snapshot taken after `set-key` and `gh-local.py auth login` contains the USAi
key and the GitHub token. Treat it as a secret. Keep it only under
`%LOCALAPPDATA%`. Never copy it to OneDrive, shared drives, Git, or chat.
Delete it when the rehearsal is over.

```powershell
# $dir is "$env:LOCALAPPDATA\engineer-wsl", as above. Save the ready (secret) snapshot:
wsl --terminate engineer-mvp
wsl --export engineer-mvp "$dir\engineer-mvp-ready.tar"

# Reset to it. Use engineer-mvp-base.tar instead to start clean.
wsl --unregister engineer-mvp
wsl --import engineer-mvp "$dir\engineer-mvp" "$dir\engineer-mvp-ready.tar" --version 2
```

After a reset, open `engineer-mvp` and run `python3 scripts/local_env.py status`.
Use the offset URLs in the demo: Forge http://127.0.0.1:19091/ and Kata
http://127.0.0.1:18777/kata.
