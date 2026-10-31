"""Fail-closed OS ownership preflight for a *disabled* push broker pilot.

This is a prerequisite, not proof of cgroup cleanup or remote-side fencing.
The caller must use a broker-owned, non-root UID distinct from the AI agent,
and a broker-owned SQLite directory not accessible for writes by that agent.
No GitHub push or credential loading is performed here.
"""
import os
import stat
from pathlib import Path


class IsolationDenied(RuntimeError):
    """Broker must not start any network transport."""


def _no_links(path):
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        raise IsolationDenied('absolute normalized path required')
    for item in (path, *path.parents):
        if item == Path('/'):
            break
        if stat.S_ISLNK(os.lstat(item).st_mode):
            raise IsolationDenied('symlink in trusted path')


def _owned_dir(path, uid):
    _no_links(path)
    info = os.stat(path)
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != uid or info.st_mode & 0o022:
        raise IsolationDenied('broker directory ownership/mode unsafe')


def _private_file(path, owners):
    _no_links(path)
    info = os.stat(path)
    if not stat.S_ISREG(info.st_mode) or info.st_uid not in owners or info.st_mode & 0o077:
        raise IsolationDenied('broker file ownership/mode unsafe')


def verify_broker_isolation(db_path, credential_path, *, agent_uid,
                            trusted_root='/var/lib/hangeul-swipji-broker'):
    """Reject shared UID, root execution, symlinks, writable DB/WAL/SHM.

    Caller must obtain agent_uid from trusted OS configuration, not agent input.
    Root-owned LoadCredential is allowed only as a private regular file.
    """
    if os.name != 'posix':
        raise IsolationDenied('POSIX broker isolation required')
    uid = os.geteuid()
    if (type(uid) is not int or type(agent_uid) is not int
            or uid <= 0 or agent_uid <= 0 or uid == agent_uid):
        raise IsolationDenied('dedicated non-root broker UID required')
    root = Path(trusted_root)
    db = Path(db_path)
    if (not root.is_absolute() or not db.is_absolute() or '..' in db.parts
            or db.parent != root or db.name in ('.', '..')):
        raise IsolationDenied('DB must be directly inside trusted broker root')
    _owned_dir(root, uid)
    _private_file(db, {uid})
    for suffix in ('-wal', '-shm', '-journal'):
        sidecar = Path(str(db) + suffix)
        if os.path.lexists(sidecar):
            _private_file(sidecar, {uid})
    _private_file(credential_path, {uid, 0})
    return True
