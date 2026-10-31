"""Fail-closed descriptor-based OS preflight for a disabled push broker.

This is NOT transport authorization. A live broker must hold verified dirfds
and credential fds throughout its operation; re-opening paths after preflight
would reintroduce TOCTOU. Remote SHA CAS and cgroup cleanup remain unproved.
"""
import os
import stat
from contextlib import contextmanager
from pathlib import Path


class IsolationDenied(RuntimeError):
    """Broker must not start any network transport."""


def _parts(path):
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        raise IsolationDenied('absolute normalized path required')
    return path.parts[1:]


def _check_directory(info, broker_uid):
    if not stat.S_ISDIR(info.st_mode) or info.st_uid not in (0, broker_uid):
        raise IsolationDenied('untrusted directory owner or type')
    if info.st_mode & 0o022:
        # /tmp and /var/tmp: only root-owned sticky directories are allowed.
        # A non-root sticky directory can still be mutated by its owner.
        if not (info.st_uid == 0 and info.st_mode & stat.S_ISVTX):
            raise IsolationDenied('writable ancestor directory')


@contextmanager
def _trusted_directory(path, broker_uid):
    """Walk from / with O_NOFOLLOW and validate opened directory fds."""
    parts = _parts(path)
    if not hasattr(os, 'O_DIRECTORY') or not hasattr(os, 'O_NOFOLLOW'):
        raise IsolationDenied('safe directory traversal unsupported')
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, 'O_CLOEXEC', 0)
    fd = None
    try:
        fd = os.open('/', flags)
        _check_directory(os.fstat(fd), broker_uid)
        for component in parts:
            next_fd = os.open(component, flags, dir_fd=fd)
            os.close(fd)
            fd = next_fd
            _check_directory(os.fstat(fd), broker_uid)
        yield fd
    except OSError as exc:
        raise IsolationDenied('unsafe or inaccessible directory path') from exc
    finally:
        if fd is not None:
            os.close(fd)


def _private_file_at(parent_fd, name, owners, *, optional=False):
    flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | getattr(os, 'O_CLOEXEC', 0)
    try:
        fd = os.open(name, flags, dir_fd=parent_fd)
    except FileNotFoundError as exc:
        if optional:
            return
        raise IsolationDenied('required broker file missing') from exc
    except OSError as exc:
        raise IsolationDenied('unsafe broker file path') from exc
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid not in owners
                or info.st_mode & 0o077):
            raise IsolationDenied('broker file ownership/mode unsafe')
    finally:
        os.close(fd)


def verify_broker_isolation(db_path, credential_path, *, agent_uid,
                            trusted_root='/var/lib/hangeul-swipji-broker'):
    """Fail closed on writable ancestors, shared UID, symlinks, or unsafe files.

    agent_uid MUST come from trusted OS configuration, not from the AI agent.
    Validation uses opened fds, but the future transport must reuse held fds
    rather than re-open paths after this check.
    """
    if os.name != 'posix':
        raise IsolationDenied('POSIX broker isolation required')
    uid = os.geteuid()
    if (type(uid) is not int or type(agent_uid) is not int
            or uid <= 0 or agent_uid <= 0 or uid == agent_uid):
        raise IsolationDenied('dedicated non-root broker UID required')
    root = Path(trusted_root)
    db = Path(db_path)
    cred = Path(credential_path)
    if (not root.is_absolute() or not db.is_absolute() or not cred.is_absolute()
            or '..' in root.parts or '..' in db.parts or '..' in cred.parts
            or db.parent != root or db.name in ('.', '..')):
        raise IsolationDenied('DB must be directly inside trusted broker root')
    with _trusted_directory(root, uid) as root_fd:
        root_info = os.fstat(root_fd)
        if root_info.st_uid != uid or root_info.st_mode & 0o022:
            raise IsolationDenied('broker directory ownership/mode unsafe')
        _private_file_at(root_fd, db.name, {uid})
        for suffix in ('-wal', '-shm', '-journal'):
            _private_file_at(root_fd, db.name + suffix, {uid}, optional=True)
    with _trusted_directory(cred.parent, uid) as cred_parent_fd:
        _private_file_at(cred_parent_fd, cred.name, {uid, 0})
    return True
