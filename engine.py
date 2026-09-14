"""
The execution engine: everything that actually shells out to `defaults`,
`pmset`, `softwareupdate`, or plain commands, plus the privilege-escalation
and revert-recording plumbing shared by every tweak in tweaks.py.

Privilege escalation
---------------------
This is a backend service, not a Terminal session -- there's no guarantee
anything is attached to a TTY that `sudo` could prompt on. Instead,
admin-requiring commands go through `osascript ... with administrator
privileges`, which pops the same native macOS password dialog every Mac
user already recognizes. That's the right UX for something a future GUI
would sit in front of, and it means this backend must never be run as root
itself -- it only asks for elevation exactly when a specific command needs
it, the same way the underlying MacDebloat.sh script does with `sudo`.
"""
from __future__ import annotations

import shlex
import subprocess
from typing import Optional

from . import history


class CommandResult:
    def __init__(self, ok: bool, stdout: str = "", stderr: str = ""):
        self.ok = ok
        self.stdout = stdout
        self.stderr = stderr

    @property
    def output(self) -> str:
        return (self.stderr or self.stdout).strip()


def _osascript_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def run_privileged(argv: list[str], timeout: int = 60) -> CommandResult:
    """Run argv with a native admin-password prompt via osascript."""
    cmd_str = " ".join(shlex.quote(a) for a in argv)
    script = f'do shell script "{_osascript_escape(cmd_str)}" with administrator privileges'
    try:
        proc = subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True, timeout=timeout
        )
        return CommandResult(proc.returncode == 0, proc.stdout, proc.stderr)
    except FileNotFoundError:
        return CommandResult(False, stderr="osascript not found -- is this running on macOS?")
    except subprocess.TimeoutExpired:
        return CommandResult(False, stderr="Timed out waiting for admin authorization")


def run_user(argv: list[str], timeout: int = 30) -> CommandResult:
    """Run argv as the current user, no elevation."""
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return CommandResult(proc.returncode == 0, proc.stdout, proc.stderr)
    except FileNotFoundError as e:
        return CommandResult(False, stderr=str(e))
    except subprocess.TimeoutExpired:
        return CommandResult(False, stderr="Command timed out")


def _run(argv: list[str], admin: bool) -> CommandResult:
    return run_privileged(argv) if admin else run_user(argv)


def defaults_read(domain: str, key: str, admin: bool = False) -> Optional[str]:
    result = _run(["defaults", "read", domain, key], admin)
    return result.stdout.strip() if result.ok else None


def defaults_read_domain(domain: str, admin: bool = False) -> Optional[str]:
    """Read every key in a domain as one text dump (`defaults read <domain>`,
    no key argument) -- used where a key name isn't known ahead of time,
    e.g. Apple Intelligence's dynamically-numbered opt-in key."""
    result = _run(["defaults", "read", domain], admin)
    return result.stdout.strip() if result.ok else None


def defaults_read_type(domain: str, key: str, admin: bool = False) -> Optional[str]:
    result = _run(["defaults", "read-type", domain, key], admin)
    return result.stdout.strip() if result.ok else None


def type_flag_for(domain: str, key: str, admin: bool = False) -> str:
    t = defaults_read_type(domain, key, admin) or ""
    if "boolean" in t:
        return "-bool"
    if "integer" in t:
        return "-int"
    if "float" in t:
        return "-float"
    if "array" in t:
        return "-array"
    if "dict" in t:
        return "-dict"
    return "-string"


def defaults_write(
    domain: str,
    key: str,
    type_flag: str,
    value: str,
    admin: bool = False,
    run_id: Optional[str] = None,
    tweak_id: str = "",
) -> tuple[bool, str]:
    """Write a defaults key. The prior value is read up front (it has to be,
    since the write is about to overwrite it), but the history row is only
    recorded once the write actually succeeds -- a failed write changed
    nothing, so it should leave nothing to revert."""
    prior = None
    prior_type = None
    if run_id:
        prior = defaults_read(domain, key, admin)
        if prior is not None:
            prior_type = type_flag_for(domain, key, admin)

    result = _run(["defaults", "write", domain, key, type_flag, value], admin)

    if run_id and result.ok:
        if prior is not None:
            history.record(
                run_id, tweak_id, "defaults_write",
                domain=domain, key=key, prior_value=prior, prior_type=prior_type,
                requires_admin=admin,
            )
        else:
            history.record(
                run_id, tweak_id, "defaults_delete",
                domain=domain, key=key, requires_admin=admin,
            )

    return result.ok, (result.output or "applied")


def restart_app(name: str) -> None:
    run_user(["killall", name])


def revert_action_row(row: tuple) -> bool:
    """row layout matches history.get_actions_for_run:
    (id, action, domain, key, prior_value, prior_type, requires_admin, revert_shell_cmd, reverted)
    """
    row_id, action, domain, key, prior_value, prior_type, requires_admin, revert_shell_cmd, reverted = row
    admin = bool(requires_admin)

    if action == "defaults_write":
        result = _run(["defaults", "write", domain, key, prior_type, prior_value], admin)
        ok = result.ok
    elif action == "defaults_delete":
        result = _run(["defaults", "delete", domain, key], admin)
        ok = result.ok or "does not exist" in result.stderr
    elif action == "shell":
        if not revert_shell_cmd or revert_shell_cmd.startswith("#"):
            # Informational only (e.g. app removal) -- nothing to run, treat as done.
            ok = True
        else:
            result = _run(shlex.split(revert_shell_cmd), admin)
            ok = result.ok
    else:
        ok = False

    if ok:
        history.mark_reverted(row_id)
    return ok
