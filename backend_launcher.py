"""
Finds or starts the deblaot backend so the GUI has something to talk to.

Expected layout (siblings, both cloned from the same repo):
    <repo>/deblaot/          <- the FastAPI backend
    <repo>/deblaot-gui/      <- this app

If a deblaot/.venv already exists (created by deblaot/run.sh), that
interpreter is used to launch uvicorn so the GUI doesn't need fastapi
installed in its own environment. Otherwise it falls back to whichever
Python is running the GUI itself, on the assumption both were installed
into one shared environment.
"""
from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


class BackendError(Exception):
    pass


def is_backend_up(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _backend_dir(gui_dir: Path) -> Path:
    return gui_dir.parent / "deblaot"


def _backend_python(gui_dir: Path) -> list[str]:
    venv_python = _backend_dir(gui_dir) / ".venv" / "bin" / "python3"
    if venv_python.exists():
        return [str(venv_python)]
    return [sys.executable]


def start_backend(
    gui_dir: Path,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    wait_seconds: float = 20,
) -> subprocess.Popen:
    """Launch uvicorn for the backend and block until it responds to a
    connection (or raise BackendError). Returns the Popen handle so the
    caller can terminate it on shutdown."""
    backend_dir = _backend_dir(gui_dir)
    if not (backend_dir / "app" / "main.py").exists():
        raise BackendError(
            f"Can't find the deblaot backend at {backend_dir}.\n"
            "This app expects 'deblaot' and 'deblaot-gui' to be sibling "
            "folders in the same repo."
        )

    argv = _backend_python(gui_dir) + [
        "-m", "uvicorn", "app.main:app", "--host", host, "--port", str(port),
    ]
    try:
        proc = subprocess.Popen(
            argv, cwd=str(backend_dir),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
    except OSError as exc:
        raise BackendError(f"Couldn't launch the backend ({exc}).") from exc

    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        if is_backend_up(host, port):
            return proc
        if proc.poll() is not None:
            output = proc.stdout.read() if proc.stdout else ""
            raise BackendError(
                "The deblaot backend process exited before it started "
                f"listening. Its output:\n{output[-2000:]}"
            )
        time.sleep(0.3)

    proc.terminate()
    raise BackendError(
        f"Timed out waiting {wait_seconds:.0f}s for deblaot to start on "
        f"{host}:{port}. Try running deblaot/run.sh manually to see what's wrong."
    )


def stop_backend(proc: subprocess.Popen, wait_seconds: float = 5) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=wait_seconds)
    except subprocess.TimeoutExpired:
        proc.kill()
