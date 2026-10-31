"""Broker-owned subprocess lifecycle fence; NOT a live GitHub push endpoint.

Use only inside a separate systemd cgroup (KillMode=control-group) with
broker-owned credentials. Never execute an agent-supplied command.
"""
import os
import signal
import subprocess
import time


class PushUncertain(RuntimeError):
    """Remote outcome or process-group quiescence not proven; never retry."""


class PushRevoked(RuntimeError):
    """Lease was revoked; process group shutdown was attempted."""


def _kill_group(pgid, *, timeout=3.0):
    """Kill and check the whole group, not merely the git parent."""
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.02)
    raise PushUncertain("process group not proven quiescent")


def supervise(command, *, lease_live, timeout=120, interval=0.05, cwd=None, env=None):
    """Run broker-constructed transport with fail-closed lease monitoring.

    lease_live MUST read broker-owned authoritative fencing state, not an
    agent-writable queue. A broker SIGKILL requires systemd cgroup cleanup;
    no Python finally handler can handle SIGKILL. The caller must reconcile
    exact remote SHA after success. This module does NOT authorize push.
    """
    if not isinstance(command, (tuple, list)) or not command or any(
            not isinstance(x, str) for x in command):
        raise ValueError("broker command must be preconstructed")
    if timeout <= 0 or timeout > 120 or interval <= 0 or interval > 1:
        raise ValueError("unsafe supervisor timing")
    if not lease_live():
        raise PushRevoked("lease not live before spawn")
    proc = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            start_new_session=True, text=True)
    pgid = proc.pid
    started = time.monotonic()
    try:
        while True:
            if not lease_live():
                raise PushRevoked("lease revoked")
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                raise PushUncertain("transport timed out")
            try:
                out, err = proc.communicate(timeout=min(interval, remaining))
                if not lease_live():
                    raise PushRevoked("lease revoked at completion")
                if proc.returncode:
                    raise PushUncertain("transport exited nonzero; remote outcome unknown")
                return subprocess.CompletedProcess(command, proc.returncode, out, err)
            except subprocess.TimeoutExpired:
                continue
    except (PushRevoked, PushUncertain):
        _kill_group(pgid)
        raise
    finally:
        if proc.poll() is None:
            _kill_group(pgid)
        proc.communicate()
