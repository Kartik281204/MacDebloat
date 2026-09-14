"""A dialog listing recent runs, each revertible individually."""
from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QMessageBox, QAbstractItemView,
)

from .api_client import ApiError
from .workers import ApiWorker


class HistoryDialog(QDialog):
    def __init__(self, client, parent=None):
        super().__init__(parent)
        self.client = client
        self._workers = []
        self.setWindowTitle("History & Revert")
        self.resize(640, 400)
        self._build_ui()
        self._reload()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        heading = QLabel("Recent runs")
        heading.setObjectName("categoryHeading")
        layout.addWidget(heading)

        note = QLabel(
            "Each row is one apply -- a single tweak, a whole category, or a "
            "preset. Reverting puts every change from that run back the way "
            "it was."
        )
        note.setWordWrap(True)
        note.setObjectName("categorySubheading")
        layout.addWidget(note)

        self.table = QTableWidget(0, 4, self)
        self.table.setHorizontalHeaderLabels(["Started", "Run ID", "Actions", ""])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        layout.addWidget(self.table)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._reload)
        button_row.addWidget(refresh_btn)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_row.addWidget(close_btn)
        layout.addLayout(button_row)

    def _keep(self, worker):
        self._workers.append(worker)
        worker.finished.connect(lambda: self._workers.remove(worker) if worker in self._workers else None)

    def _reload(self):
        worker = ApiWorker(self.client.history_runs, limit=30)
        worker.succeeded.connect(self._on_runs_loaded)
        worker.failed.connect(self._on_error)
        self._keep(worker)
        worker.start()

    def _on_error(self, message: str):
        QMessageBox.warning(self, "Couldn't load history", message)

    def _on_runs_loaded(self, runs: list):
        self.table.setRowCount(len(runs))
        for row_index, run in enumerate(runs):
            self.table.setItem(row_index, 0, QTableWidgetItem(run.get("started", "")))
            self.table.setItem(row_index, 1, QTableWidgetItem(run.get("run_id", "")))

            action_count = run.get("action_count", 0)
            reverted_count = run.get("reverted_count", 0)
            status = f"{action_count} change(s)"
            if reverted_count:
                status += f" -- {reverted_count} reverted"
            self.table.setItem(row_index, 2, QTableWidgetItem(status))

            revert_btn = QPushButton("Revert")
            fully_reverted = action_count > 0 and reverted_count >= action_count
            revert_btn.setEnabled(not fully_reverted)
            revert_btn.clicked.connect(lambda _checked, rid=run.get("run_id"): self._revert(rid))
            self.table.setCellWidget(row_index, 3, revert_btn)

    def _revert(self, run_id: str):
        confirm = QMessageBox.question(
            self, "Revert this run?",
            f"Undo every change made in run {run_id}?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        worker = ApiWorker(self.client.revert, run_id=run_id)
        worker.succeeded.connect(self._on_reverted)
        worker.failed.connect(self._on_error)
        self._keep(worker)
        worker.start()

    def _on_reverted(self, result: dict):
        errors = result.get("errors") or []
        message = f"Reverted {result.get('reverted_count', 0)} change(s)."
        if errors:
            message += "\n\nSome actions couldn't be reverted:\n" + "\n".join(errors)
            QMessageBox.warning(self, "Revert finished with errors", message)
        else:
            QMessageBox.information(self, "Reverted", message)
        self._reload()
