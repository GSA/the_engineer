"""Explicit local routing, never project identity attestation."""
from dataclasses import dataclass, fields
import json
import math
import os
from pathlib import Path


def exact_fields(value, required, optional=()):
    if not isinstance(value, dict) or set(value) - set(required) - set(optional) or set(required) - set(value):
        raise ValueError('invalid object fields')


def identity(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 512:
        raise ValueError('invalid identity')
    return value


@dataclass(frozen=True)
class TaskBinding:
    daemon_id: str
    project_uid: str
    issue_uid: str
    workspace_id: str


def parse_task(value):
    names = [f.name for f in fields(TaskBinding)]
    exact_fields(value, names)
    return TaskBinding(**{name: identity(value[name]) for name in names})


@dataclass(frozen=True)
class Limits:
    timeout_seconds: float = 30
    max_bytes: int = 1048576
    max_business_locators: int = 10
    max_code_queries: int = 10


@dataclass(frozen=True)
class LibrarianBinding:
    project_id: str
    executable: Path
    root: Path
    # Only a legacy release takes its reader CLI as an argument; the current
    # toolkit loads that module from its own root.
    reader: Path | None = None
    selection: Path | None = None


@dataclass(frozen=True)
class KnowitallBinding:
    project_id: str
    repository_id: str
    python: Path
    store: Path


@dataclass(frozen=True)
class ConsumerConfig:
    librarian: LibrarianBinding
    knowitall: KnowitallBinding | None = None
    limits: Limits = Limits()


def load_config(path: Path) -> ConsumerConfig:
    path = Path(path).resolve()
    if path.stat().st_size > 1048576:
        raise ValueError('configuration too large')
    value = json.loads(path.read_text(encoding='utf-8'))
    exact_fields(value, ['schema', 'librarian'], ['knowitall', 'limits'])
    if value['schema'] != 'engineer.context-config/v1':
        raise ValueError('unsupported configuration schema')

    def local_path(raw):
        identity(raw)
        if any(c in raw for c in ('\n', '\r', '\x00')):
            raise ValueError('invalid path')
        return (path.parent / raw).resolve()

    def program_path(raw):
        # Programs keep the selected link: a virtual environment's interpreter
        # must run through its own path so its prefix stays that environment.
        # Traversal is still collapsed lexically against the configuration root.
        identity(raw)
        if any(c in raw for c in ('\n', '\r', '\x00')):
            raise ValueError('invalid path')
        return Path(os.path.normpath(path.parent / raw))

    lib = value['librarian']; code = value.get('knowitall')
    exact_fields(lib, ['project_id', 'executable', 'root'], ['reader', 'selection'])
    knowitall = None
    if code is not None:
        exact_fields(code, ['project_id', 'repository_id', 'python', 'store'])
        knowitall = KnowitallBinding(identity(code['project_id']), identity(code['repository_id']),
                                     program_path(code['python']), local_path(code['store']))
    librarian = LibrarianBinding(identity(lib['project_id']), program_path(lib['executable']),
                                 local_path(lib['root']),
                                 local_path(lib['reader']) if lib.get('reader') is not None else None,
                                 local_path(lib['selection']) if lib.get('selection') is not None else None)
    if librarian.selection is not None and not librarian.selection.is_relative_to(librarian.root):
        raise ValueError('selection outside business root')
    limits = value.get('limits', {})
    exact_fields(limits, [], [f.name for f in fields(Limits)])
    for name, number in limits.items():
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number) or number <= 0:
            raise ValueError('invalid resource limit')
        if name != 'timeout_seconds' and not isinstance(number, int):
            raise ValueError('integer resource limit required')
    return ConsumerConfig(librarian, knowitall, Limits(**limits))
