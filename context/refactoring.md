# Deletion-first cleanup refinement

**Date:** 2026-10-26. **Tracking:** engi-platform `ycns`.
**Status:** first source cleanup implemented in `rzsc`: one installer service
inventory and explicit private Kata storage across manual, unit and supervisor
startup. Remaining slices are still backlog; review/commit evidence belongs to
the native task. [Architecture](system-architecture.md) remains the ownership baseline.

**Resolved lifecycle, 17:03:** Forge is required to launch/manage coding and
review agents. Keep four managed services and preserve its ongoing
reimplementation; restoration is separately tracked in `7pq7` and committed
as `bc00164`. The three-service cleanup and dormant/optional-Forge proposal
are withdrawn. One installation profile and one service owner are simpler
than adding a core-only variant or migrating a working daemon.

The upstream [README](../forge/README.md#start) documents `daemon start` for
standalone background startup and `serve` for foreground execution. This
environment already runs the latter through `forge-run` under user systemd,
with automatic startup/restart and the existing private profile. Keep systemd
as lifecycle owner; do not also run `daemon start/restart/stop` for that profile.
No second daemon, new supervisor or startup migration is needed.

## Direction

The owner prioritizes safe refactoring and lower complexity before memory
service trials. Native Kata owns work; roborev reviews changes. Tests are not
a ceremonial requirement: use them where they protect observable behavior,
stored-data compatibility or configuration/lifecycle boundaries.

This is an architectural program, not one giant refactor. Superpowers
brainstorming supplies the decomposition and approval gates. The first
installer correction is small enough for a bounded design; provider/packaging
changes need their own design before implementation. Do not generate a long
TDD script or dispatch parallel writers before those interfaces are settled.

Prefer deleting obsolete branches, unnecessary dependencies and repeated
operating instructions. Do not replace a few literals with a plugin registry,
turn every helper into a class, split files only because they are large, or
introduce a shared runtime that violates instance isolation. Fewer lines are
not a win if understanding compatibility becomes harder.

For each implemented slice, record the old and new command/configuration paths,
the code or dependency that disappeared, the preserved behavior, and the
verification/review evidence. A net line reduction is useful evidence, not a
quota that licenses removing safeguards.

## Findings that determine the cuts

| Finding | Consequence |
| --- | --- |
| `dist/install.py` repeats service lists; `install-forge-service` is restored in `bc00164` | Consolidate repeated lists and add actual CLI parity checks. Keep the four-service test requirement; mocks alone previously hid drift. |
| `local_env.py::SERVICE_PORTS` now identifies four managed services | Preserve Kata, roborev, AgentsView and Forge; no new supervisor/service framework is needed. |
| Manual/unit Kata startup sets only `KATA_HOME`; environment overrides and stored `[storage].dsn` outrank its default | Pin an explicit managed `KATA_DSN` and clear legacy `KATA_DB` for managed startup; ordinary native CLI behavior stays unrestricted. |
| Installer builds Kata without provisioning the documented user CLI entrypoint/native client configuration | Track fresh-host discovery and intended-daemon selection explicitly, rather than relying on this host's existing setup. |
| Installer/setup require a Forge binary/config | This matches the owner's required execution component. Retain the single profile; optional packaging would add complexity without a current requirement. |
| Setup and preflight each assume the legacy Falcon MCP executable | Define one explicit supplied-provider contract; do not add filename guessing or compatibility aliases. |
| Mandatory project/tools/status context totaled 371,851 bytes before this investigation | Separate current operating guidance from preserved dated history. The README still repeats superseded generated-task-index guidance. |
| Toolkit and Falcon generic code is mostly divergent, not a clean duplicated library | Inventory contract and instance extensions before considering consolidation; full independent clones remain the current topology. |
| SPUD local Jira/Confluence CLI branches duplicate post-export render/package flow | First establish whether supported standalone exporters already satisfy machine intake; do not fork a new connector or make upstream changes our task. |
| SPUD already has pipeline manifest code and extensive ingestion/packaging stories | Check existing schemas and backlog before designing another artifact manifest or duplicating upstream work. |

Direct Engineer inspection covered `dist/install.py`, its tests,
`scripts/local_env.py`, `scripts/smoke.py`, launcher/import relationships,
current README and existing Katas. File size alone is not a refactoring case.

Two read-only scouts examined the independent neighboring scopes. They made
no edits. Their initial recommendations were challenged for net complexity:

- **Reject XLSX helper extraction for now.** Falcon v1/v2 share only roughly
  50-60 helper lines worth considering; current v2 already delegates legacy
  registration. Moving v1 dependencies risks fingerprint-bound historical
  verification and adds another dependency to understand.
- **Retain direct-source coverage adapter loading.** The existing explicit
  map, symlink refusal and compile-from-bytes path avoid import/pycache
  behavior. A typed registry would add machinery and change those semantics,
  not simply remove complexity.
- **Do not share a toolkit checkout across instances.** Decisions 0003/0004
  protect distinct policy, store layouts and index identities. Identical
  `compact_records.py` bytes are a parity observation, not permission to
  introduce cross-checkout imports.

These are deliberate non-changes, not missed cleanup opportunities.

## Refined native backlog

Nine backlog items were created after inspecting existing work. First slice
`rzsc` is implemented; seven other slices remain and optional-Forge proposal
`k79n` was closed `wontfix`. Refinement task `ycns` is separate. This table is a
dated navigation aid; live task bodies/status/dependencies remain in Kata.

| Repository | Kata | Deliverable |
| --- | --- | --- |
| kenn-kopy | `engi-platform#rzsc` | Implemented in a650c44: one four-service installer inventory, runtime CLI parity and private Kata startup |
| kenn-kopy | `engi-platform#f47m` | Explicit Librarian executable/reader/root/selection binding shared by preflight and setup |
| kenn-kopy | `engi-platform#k79n` | Closed `wontfix`: optional/dormant-Forge packaging is unnecessary; Forge is required |
| kenn-kopy | `engi-platform#qc96` | Current operating guidance separated from preserved dated history; proposed mandatory-entrypoint budget <=16 KiB each |
| kenn-kopy | `engi-platform#0sfx` | Design opt-in native Kata CLI/client provisioning, with fresh synthetic-home discovery, daemon selection and collision handling |
| the_librarian | `librarian#7bna` | Generic-module/instance-divergence matrix and safe consolidation candidates, without adopting shared runtime |
| the_librarian | `librarian#55nx` | Receiving contract for supplied SPUD exports using existing inbox/catalog/extraction/selection boundaries |
| falcon-docs | `falcon-docs#939r` | Compatibility map protecting legacy verification, current preparation and intentional coverage loading |
| aos-spud | `spud#3sv9` | Local producer contract/Markdown-only compatibility investigation; no upstream source changes or publication |

Owner-approved task separation at 17:55 on October 26 now binds the toolkit to
`librarian` and the populated instance to `falcon-docs`. Native moves preserve
issue UIDs, history and cross-project links. Existing repo metadata/title
prefixes remain descriptive, not Forge routing.

Actual prerequisite: **`spud#3sv9` blocks `librarian#55nx`**, because receiving
design consumes the producer contract evidence. `55nx` is a child of existing
automation roadmap `falcon-docs#51kq`; that does not activate unattended processing.
The installer slices are children of `p4ke`; `5xrm` retains full reproduction.
Shared files require serialized writes, not invented logical dependency edges.

Existing `vkye -> 1dkw` still gates retirement of the temporary Forge build.
The previous memory research stays complete, but no memory product trial is
started. Graph visualization, cloud, sandboxing and unrelated demo work are
not silently cancelled or promoted.

## First implemented slice: rzsc

Use the restored runtime's four-service boundary: Kata, roborev, AgentsView
and Forge. Consolidate managed-service names inside the installer and use them
consistently for opt-in unit installation, applicable unit conflict checks,
prompts and managed stop instructions. Preserve `install-forge-service`,
automatic service startup and the foreground fallback. Do not duplicate the
ongoing Forge reimplementation or create a competing daemon lifecycle.

Do not introduce a cross-module service registry. A small explicit installer
list plus a parity check against the existing runtime contract is simpler than
a framework, especially because standalone `dist/` may be used before the
target checkout exists. Preserve the installation order deliberately.

Touch `dist/install.py`, Kata unit environment generation in
`scripts/local_env.py`, the directly related tests, `dist/README.md` and
affected current root README statements. Preserve manual/noninteractive
defaults, foreign-unit refusal, quoting of paths with spaces, native Kata,
loopback ports, private state, and explicit Forge capability. Do not change
running units, remove Forge files or claim the full installer is fixed: the
provider-path and fresh-host native CLI/client-provisioning issues are
separate. Existing Forge build-workaround retirement remains `vkye`/`1dkw`.

Managed foreground and systemd startup must replace inherited `KATA_DSN` with
the absolute private `.local/environment/kata/kata.db` path and clear legacy
`KATA_DB`. Merely clearing both variables is insufficient: native
`kata/internal/config/dsn_resolve.go` resolves environment overrides, then
stored `[storage].dsn`, then the `KATA_HOME` default. The explicit managed
`KATA_DSN` must win without rewriting retained configuration. Keep this scoped
to managed process startup; do not restore a custom CLI dispatcher or modify
global user settings.

Useful verification is narrow: check emitted install commands against actual
runtime CLI support, cover manual versus opt-in behavior, preserve foreign-unit
and path-quoting checks, and confirm one lifecycle owner per service. Synthetic
inherited-variable and conflicting stored-DSN checks must establish the
database selected by both emitted foreground commands and generated unit
environments, not merely match a `KATA_HOME` string; no alternate database may
be opened. Retain the four-service requirement while improving verification
beyond mocked command strings. No real service restart or full download/build
is needed for this slice.

The owner resumed implementation at 17:12. Repeated installer service lists
are now one ordered tuple, with a pre-mutation runtime-parity guard. Unit and
supervisor startup reuse one scoped Kata environment helper; the redundant
second Kata command validation was removed. Focused checks include actual
isolated native Kata launches from printed commands and generated-unit settings.
No live service was restarted or unit regenerated. Larger provider changes
remain separate; optional Forge packaging is not on the execution path.

## Review and execution discipline

Design review 76 reported two omitted native Kata reproduction requirements.
Both were confirmed against local source: `rzsc` now owns managed storage
environment isolation, and new `0sfx` owns fresh-host CLI/client provisioning.
Review 77 identified that clearing environment overrides alone still permits a
stored DSN redirect. The revised contract explicitly pins managed `KATA_DSN`
and includes conflicting stored configuration in acceptance. These are refined
acceptance requirements; the Kata startup fix is now implemented under `rzsc`,
while fresh-host native client provisioning remains open.
Review 78 passed the earlier design before the lifecycle clarification; it is
not approval of a three-service implementation now. This revision preserves
its independent safeguards while correcting the service boundary.

One implementation writer per overlapping file set. Parallelize independent
read-only investigation or truly disjoint approved changes, not overlapping
installer/runtime edits. Search, claim the exact Kata, preserve dirty state, perform
one bounded change, and review that exact diff with managed roborev/Pi.

Read the stored result, not only command exit status. Resolve material findings
and re-review changed code; close only the delivered slice with persistent
evidence. Existing per-repository gates remain enabled. A review does not grant
publication, corpus mutation or task migration.

Documentation-only work needs link/consistency inspection and review, not a
runtime suite. Configuration, process ownership and persisted extraction
compatibility justify focused automated checks. No removal of existing
regressions merely because TDD is not mandatory.

No new framework, memory service, remote connector, deployment, rename,
authority-store write or neighboring code edit is part of this refinement.
