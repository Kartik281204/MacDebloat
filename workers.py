"""
A single reusable QThread subclass for running any blocking call (an API
request, or the backend-launch check) off the UI thread. PyQt5 GUIs freeze
-- and macOS will flag them as "not responding" -- if a slot handler blocks
for more than a fraction of a second, and applying a tweak can legitimately
take tens of seconds if it pops a native admin-password prompt.

Usage:
    worker = ApiWorker(client.apply_tweak, "dark-mode")
    worker.succeeded.connect(self._on_applied)
    worker.failed.connect(self._on_apply_failed)
    self._keep_alive(worker)   # see MainWindow._run -- prevents GC mid-flight
    worker.start()
"""
from __future__ import annotations

from PyQt5.QtCore import QThread, pyqtSignal


class ApiWorker(QThread):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self) -> None:
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as exc:  # noqa: BLE001 -- surfaced to the UI, not swallowed
            self.failed.emit(str(exc))
            return
        self.succeeded.emit(result)
