"""Linux cgroup-v2 placement preflight for a future isolated push broker.

This is an OS placement check, NOT a transport permission or SIGKILL proof.
A separate root-owned systemd unit with KillMode=control-group, Delegate=no,
separate credentials/UID, and independent B host fault-injection remain required.
No GitHub push is enabled by this module.
"""
import os
import re
import sys
from pathlib import Path


class CgroupDenied(RuntimeError):
    """The broker must not start a remote transport."""


def _membership(path):
    try:
        rows = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise CgroupDenied("cgroup membership unavailable") from exc
    unified = [row[3:] for row in rows if row.startswith("0::")]
    if len(unified) != 1:
        raise CgroupDenied("unified cgroup v2 membership required")
    group = unified[0]
    if (not group.startswith("/") or group == "/"
            or any(part in ("", ".", "..") for part in group[1:].split("/"))
            or not re.fullmatch(r"/[A-Za-z0-9_.@/-]+", group)):
        raise CgroupDenied("invalid cgroup path")
    return group


def _cgroup_path(root, relative):
    """Do not follow an attacker-controlled symlink outside the kernel mount."""
    root = Path(root)
    path = root.joinpath(relative.lstrip("/"))
    try:
        if os.path.realpath(path) != os.path.normpath(path):
            raise CgroupDenied("cgroup symlink or path substitution")
        if os.path.commonpath((os.path.realpath(root), os.path.realpath(path))) != os.path.realpath(root):
            raise CgroupDenied("cgroup path escaped root")
    except (ValueError, OSError) as exc:
        raise CgroupDenied("invalid cgroup filesystem") from exc
    return path


def verify_cgroup_placement(*, agent_pid, broker_pid=None,
                            proc_root="/proc", cgroup_root="/sys/fs/cgroup",
                            unit="hangeul-push-broker.service"):
    """Fail closed unless broker and agent occupy disjoint cgroup-v2 subtrees.

    This preflight does not itself enforce KillMode or prevent a process from
    moving between delegated groups; the trusted host service manager must do so.
    """
    if sys.platform != "linux":
        raise CgroupDenied("Linux cgroup v2 required")
    if type(agent_pid) is not int or agent_pid <= 1:
        raise CgroupDenied("trusted agent PID required")
    if broker_pid is None:
        broker_pid = os.getpid()
    if type(broker_pid) is not int or broker_pid <= 1 or broker_pid == agent_pid:
        raise CgroupDenied("separate broker and agent PIDs required")
    if unit != "hangeul-push-broker.service":
        raise CgroupDenied("unapproved broker unit")
    root = Path(cgroup_root)
    if not (root / "cgroup.controllers").is_file():
        raise CgroupDenied("cgroup v2 mount unavailable")
    broker = _membership(Path(proc_root) / str(broker_pid) / "cgroup")
    agent = _membership(Path(proc_root) / str(agent_pid) / "cgroup")
    if not broker.endswith("/" + unit):
        raise CgroupDenied("broker outside dedicated systemd unit")
    if (broker == agent or broker.startswith(agent + "/")
            or agent.startswith(broker + "/")):
        raise CgroupDenied("agent and broker cgroup trees overlap")
    broker_dir = _cgroup_path(root, broker)
    _cgroup_path(root, agent)
    if not (broker_dir / "cgroup.kill").is_file():
        raise CgroupDenied("kernel cgroup.kill unavailable")
    try:
        members = (broker_dir / "cgroup.procs").read_text(encoding="ascii").split()
    except OSError as exc:
        raise CgroupDenied("cannot prove broker process membership") from exc
    if str(broker_pid) not in members:
        raise CgroupDenied("broker PID missing from expected cgroup")
    return {"broker_cgroup": broker, "agent_cgroup": agent, "kernel_kill_available": True}
