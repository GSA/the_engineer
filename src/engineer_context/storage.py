"""Explicit private, atomic persistence for sensitive observations."""
import json
import os
from pathlib import Path
import stat
import tempfile
from .packet import canonical_bytes


def _path(path):
    path=Path(os.path.abspath(path))
    for item in [path,*path.parents]:
        if item.is_symlink(): raise ValueError('symlink path refused')
    return path


def read_private_json(path,max_bytes):
    path=_path(path)
    with path.open('rb') as stream:
        data=stream.read(max_bytes+1)
    if len(data)>max_bytes: raise ValueError('input exceeded budget')
    result=json.loads(data)
    if not isinstance(result,dict): raise ValueError('JSON object required')
    canonical_bytes(result)
    return result


def write_private_json(path,value,max_bytes):
    data=canonical_bytes(value)+b'\n'
    if len(data)>max_bytes: raise ValueError('output exceeded budget')
    path=_path(path)
    missing=[]; parent=path.parent
    while not parent.exists(): missing.append(parent); parent=parent.parent
    for directory in reversed(missing): directory.mkdir(mode=0o700)
    info=path.parent.stat()
    if info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)&0o077:
        raise ValueError('private owned output directory required')
    fd,name=tempfile.mkstemp(prefix='.context-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        _path(path)
        os.replace(name,path)
    finally:
        if os.path.exists(name): os.unlink(name)
