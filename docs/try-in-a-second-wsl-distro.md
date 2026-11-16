# Try Engineer in a second WSL distro

Use this to test Engineer, or a new Engineer version, on a clean Ubuntu without
touching an existing install. It creates a second WSL2 distro, `engineer-test`,
on the same Windows computer. The distro has its own files, account and services.

## Ports are shared with your other distros

All WSL2 distros run inside one VM and share one network
([Microsoft: What is WSL](https://learn.microsoft.com/windows/wsl/about)), so
`127.0.0.1` in `engineer-test` is the same `127.0.0.1` as in your main distro.
If Engineer already runs in another distro, shift every port by setting
`ENGINEER_PORT_OFFSET=1000` before you install. The installer saves the offset,
and later commands use it automatically.

| Service | Default | Offset 1000 |
| --- | --- | --- |
| Forge (MCP) | 18091 (18092) | 19091 (19092) |
| Kata | 17777 | 18777 |
| roborev API, UI | 17373, 17374 | 18373, 18374 |
| AgentsView | 18080 | 19080 |

## Create a clean distro

This needs WSL 2.4.10 or later; check with `wsl --version`. Run these commands in
PowerShell. Keep the files under `%LOCALAPPDATA%`, which OneDrive does not sync.

```powershell
$dir = "$env:LOCALAPPDATA\engineer-wsl"
New-Item -ItemType Directory -Force -Path $dir
wsl --install Ubuntu-24.04 --name engineer-test --location "$dir\engineer-test"
```

The first launch asks for a user name and password. Set a real password,
because `sudo` asks for it. Without Microsoft Store access, download the
`ubuntu-24.04.*-wsl-amd64.wsl` image and `SHA256SUMS` from
https://releases.ubuntu.com/noble/, check the hash, then run
`wsl --install --from-file <image>.wsl --name engineer-test --location "$dir\engineer-test"`.

Save a clean baseline from PowerShell. It holds only the stock image and your
account.

```powershell
wsl --terminate engineer-test
wsl --export engineer-test "$dir\engineer-test-base.tar"
```

## Install inside `engineer-test`

```sh
echo 'export ENGINEER_PORT_OFFSET=1000' >> ~/.bashrc   # only when another distro runs Engineer
echo 'export KATA_SERVER=http://127.0.0.1:18777' >> ~/.bashrc
source ~/.bashrc
git clone https://github.com/GSA/the_engineer.git ~/engineer && cd ~/engineer
./engineer install
```

`./engineer install` may offer to turn on systemd and ask you to restart the
distro. If it does, run `wsl --terminate engineer-test` in PowerShell, reopen the
distro and run `./engineer install` again.

## Snapshots and reset

A snapshot taken after `./engineer key` and `./engineer login` contains your
USAi key and GitHub token. Treat it as a secret: keep it under
`%LOCALAPPDATA%` only, never copy it to OneDrive, shared drives, Git or chat, and
delete it when you are done.

```powershell
wsl --terminate engineer-test
wsl --export engineer-test "$dir\engineer-test-ready.tar"
# Reset (use engineer-test-base.tar to start clean):
wsl --unregister engineer-test
wsl --import engineer-test "$dir\engineer-test" "$dir\engineer-test-ready.tar" --version 2
```

To remove the test distro completely, run `wsl --unregister engineer-test`.
