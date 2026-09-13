"""
macOS system-info helpers.

Kept dependency-free (stdlib + subprocess only) so this module works even
before the rest of the app is wired up, and so it degrades gracefully on
non-macOS systems during development.
"""
from __future__ import annotations

import platform
import socket
import subprocess


def is_macos() -> bool:
    return platform.system() == "Darwin"


def is_apple_silicon() -> bool:
    return platform.machine() == "arm64"


def _sw_vers(flag: str) -> str | None:
    try:
        out = subprocess.run(
            ["sw_vers", flag], capture_output=True, text=True, timeout=5
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def macos_version() -> str:
    return _sw_vers("-productVersion") or "unknown"


def macos_build() -> str:
    return _sw_vers("-buildVersion") or "unknown"


def macos_major() -> int | None:
    version = macos_version()
    try:
        return int(version.split(".")[0])
    except (ValueError, IndexError):
        return None


def get_system_info() -> dict:
    return {
        "is_macos": is_macos(),
        "macos_version": macos_version(),
        "macos_build": macos_build(),
        "arch": platform.machine(),
        "is_apple_silicon": is_apple_silicon(),
        "hostname": socket.gethostname(),
    }
