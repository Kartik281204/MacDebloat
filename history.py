"""
Structured, queryable history of every change deblaot makes, backing the
revert feature. This replaces MacDebloat.sh's flat text log with a small
SQLite database -- each individual `defaults` write (or non-defaults shell
action, like a pmset change) gets one row recording exactly what it takes to
put that one setting back the way it was.

Every apply groups its rows under a `run_id` so a whole run (one tweak, one
category, or a whole preset) can be reverted together, or you can dig into
`list_runs` / `get_actions_for_run` to see exactly what changed.
"""
from __future__ import annotations

import datetime
import os
import sqlite3
from pathlib import Path
from typing import Optional

DB_PATH = Path(os.environ.get("DEBLAOT_HOME", Path.home() / ".deblaot")) / "history.sqlite3"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS revert_actions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT NOT NULL,
    run_id          TEXT NOT NULL,
    tweak_id        TEXT NOT NULL,
    action          TEXT NOT NULL,   -- 'defaults_write' | 'defaults_delete' | 'shell'
    domain          TEXT,
    key             TEXT,
    prior_value     TEXT,
    prior_type      TEXT,            -- e.g. '-bool', '-string' (the flag `defaults write` needs)
    requires_admin  INTEGER NOT NULL DEFAULT 0,
    revert_shell_cmd TEXT,           -- for 'shell' actions: the exact command that undoes it
    note            TEXT,
    reverted        INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_revert_actions_run_id ON revert_actions(run_id);
"""


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(_SCHEMA)
    return conn


def new_run_id() -> str:
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{os.urandom(3).hex()}"


def record(
    run_id: str,
    tweak_id: str,
    action: str,
    domain: Optional[str] = None,
    key: Optional[str] = None,
    prior_value: Optional[str] = None,
    prior_type: Optional[str] = None,
    requires_admin: bool = False,
    revert_shell_cmd: Optional[str] = None,
    note: Optional[str] = None,
) -> int:
    conn = _connect()
    try:
        cur = conn.execute(
            """INSERT INTO revert_actions
               (timestamp, run_id, tweak_id, action, domain, key,
                prior_value, prior_type, requires_admin, revert_shell_cmd, note, reverted)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,0)""",
            (
                datetime.datetime.now().isoformat(timespec="seconds"),
                run_id,
                tweak_id,
                action,
                domain,
                key,
                prior_value,
                prior_type,
                int(requires_admin),
                revert_shell_cmd,
                note,
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_runs(limit: int = 20) -> list[tuple]:
    conn = _connect()
    try:
        return conn.execute(
            """SELECT run_id, MIN(timestamp), COUNT(*), SUM(reverted)
               FROM revert_actions GROUP BY run_id
               ORDER BY MIN(timestamp) DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    finally:
        conn.close()


def get_actions_for_run(run_id: str) -> list[tuple]:
    conn = _connect()
    try:
        return conn.execute(
            """SELECT id, action, domain, key, prior_value, prior_type,
                      requires_admin, revert_shell_cmd, reverted
               FROM revert_actions WHERE run_id = ? ORDER BY id DESC""",
            (run_id,),
        ).fetchall()
    finally:
        conn.close()


def latest_run_id() -> Optional[str]:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT run_id FROM revert_actions ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def mark_reverted(action_id: int) -> None:
    conn = _connect()
    try:
        conn.execute("UPDATE revert_actions SET reverted = 1 WHERE id = ?", (action_id,))
        conn.commit()
    finally:
        conn.close()
