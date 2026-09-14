from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QListWidget, QListWidgetItem, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QFrame, QScrollArea, QComboBox,
    QPlainTextEdit, QMessageBox, QSizePolicy, QSpacerItem,
)

from . import backend_launcher
from .api_client import DeblaotClient, ApiError
from .workers import ApiWorker
from .history_dialog import HistoryDialog

APP_TITLE = "deblaot"


class MainWindow(QMainWindow):
    def __init__(self, gui_dir: Path):
        super().__init__()
        self.gui_dir = gui_dir
        self.client = DeblaotClient()
        self._backend_proc = None
        self._we_started_backend = False
        self._workers: list[ApiWorker] = []
        self._categories: list[dict] = []
        self._current_category: Optional[str] = None
        self._apply_buttons_by_tweak: dict[str, QPushButton] = {}
        self._result_labels_by_tweak: dict[str, QLabel] = {}

        self.setWindowTitle(APP_TITLE)
        self.resize(980, 640)
        self._build_ui()
        self._start_backend_then_load()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        central = QWidget(self)
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())

        body = QWidget(central)
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        body_layout.addWidget(self._build_sidebar(), 0)
        body_layout.addWidget(self._build_detail_pane(), 1)
        root.addWidget(body, 1)

        root.addWidget(self._build_log_bar())

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("headerBar")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 14, 20, 14)

        title_col = QVBoxLayout()
        title = QLabel(APP_TITLE)
        title.setObjectName("appTitle")
        title_col.addWidget(title)
        self.system_info_label = QLabel("Connecting…")
        self.system_info_label.setObjectName("systemInfo")
        title_col.addWidget(self.system_info_label)
        layout.addLayout(title_col)

        layout.addStretch(1)

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        layout.addWidget(self.status_label)

        history_btn = QPushButton("History && Revert")
        history_btn.clicked.connect(self._open_history_dialog)
        layout.addWidget(history_btn)

        return header

    def _build_sidebar(self) -> QWidget:
        container = QWidget()
        container.setFixedWidth(240)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = QListWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.currentItemChanged.connect(self._on_category_row_changed)
        layout.addWidget(self.sidebar, 1)

        actions = QWidget()
        actions.setObjectName("sidebarActions")
        actions_layout = QVBoxLayout(actions)
        actions_layout.setContentsMargins(12, 12, 12, 12)
        actions_layout.setSpacing(8)

        recommended_btn = QPushButton("Run Recommended Preset")
        recommended_btn.setProperty("class", "primary")
        recommended_btn.clicked.connect(self._on_run_recommended_clicked)
        actions_layout.addWidget(recommended_btn)

        everything_btn = QPushButton("Run Everything")
        everything_btn.clicked.connect(self._on_run_everything_clicked)
        actions_layout.addWidget(everything_btn)

        layout.addWidget(actions)
        return container

    def _build_detail_pane(self) -> QWidget:
        pane = QWidget()
        pane.setObjectName("detailPane")
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        heading_row = QHBoxLayout()
        heading_col = QVBoxLayout()
        self.category_heading = QLabel("Loading…")
        self.category_heading.setObjectName("categoryHeading")
        heading_col.addWidget(self.category_heading)
        self.category_subheading = QLabel("")
        self.category_subheading.setObjectName("categorySubheading")
        heading_col.addWidget(self.category_subheading)
        heading_row.addLayout(heading_col)
        heading_row.addStretch(1)

        self.apply_category_btn = QPushButton("Apply all in this category")
        self.apply_category_btn.setProperty("class", "primary")
        self.apply_category_btn.clicked.connect(self._on_apply_category_clicked)
        self.apply_category_btn.setEnabled(False)
        heading_row.addWidget(self.apply_category_btn)
        layout.addLayout(heading_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.tweaks_container = QWidget()
        self.tweaks_container.setObjectName("tweaksContainer")
        self.tweaks_layout = QVBoxLayout(self.tweaks_container)
        self.tweaks_layout.setContentsMargins(0, 8, 4, 8)
        self.tweaks_layout.setSpacing(10)
        self.tweaks_layout.addStretch(1)
        scroll.setWidget(self.tweaks_container)
        layout.addWidget(scroll, 1)

        return pane

    def _build_log_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("logBar")
        bar.setFixedHeight(140)
        layout = QVBoxLayout(bar)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(2)

        title = QLabel("ACTIVITY")
        title.setObjectName("logBarTitle")
        title.setContentsMargins(20, 0, 0, 0)
        layout.addWidget(title)

        self.log_console = QPlainTextEdit()
        self.log_console.setObjectName("logConsole")
        self.log_console.setReadOnly(True)
        layout.addWidget(self.log_console, 1)
        return bar

    # ------------------------------------------------------------------
    # Worker plumbing
    # ------------------------------------------------------------------

    def _keep(self, worker: ApiWorker):
        self._workers.append(worker)
        worker.finished.connect(lambda: self._workers.remove(worker) if worker in self._workers else None)

    def _run(self, fn, on_success, on_error=None, *args, **kwargs):
        worker = ApiWorker(fn, *args, **kwargs)
        worker.succeeded.connect(on_success)
        worker.failed.connect(on_error or self._default_error_handler)
        self._keep(worker)
        worker.start()
        return worker

    def _default_error_handler(self, message: str):
        self._log(message, level="error")

    def _log(self, message: str, level: str = "info"):
        prefix = {"info": "·", "success": "✓", "error": "✗"}.get(level, "·")
        self.log_console.appendPlainText(f"{prefix} {message}")

    # ------------------------------------------------------------------
    # Startup sequence: find/launch backend, then load data
    # ------------------------------------------------------------------

    def _start_backend_then_load(self):
        self.status_label.setText("Starting backend…")
        self._run(self._ensure_backend, self._on_backend_ready, self._on_backend_failed)

    def _ensure_backend(self) -> bool:
        """Runs off the UI thread. Returns True if *we* had to start it."""
        if backend_launcher.is_backend_up():
            return False
        self._backend_proc = backend_launcher.start_backend(self.gui_dir)
        return True

    def _on_backend_ready(self, we_started: bool):
        self._we_started_backend = we_started
        self.status_label.setText("Connected")
        self._log("Connected to deblaot backend" + (" (started it myself)" if we_started else " (already running)"), "success")
        self._load_system_and_categories()

    def _on_backend_failed(self, message: str):
        self.status_label.setText("Backend unavailable")
        self._log(message, "error")
        QMessageBox.critical(
            self, "Couldn't start deblaot",
            message + "\n\nYou can also run deblaot/run.sh yourself in a "
            "terminal, then reopen this app.",
        )

    def _load_system_and_categories(self):
        self._run(self.client.system_info, self._on_system_info)
        self._run(self.client.categories, self._on_categories)

    def _on_system_info(self, info: dict):
        arch = "Apple Silicon" if info.get("is_apple_silicon") else info.get("arch", "")
        bits = [b for b in [info.get("hostname"), f"macOS {info.get('macos_version')}", arch] if b and b != "unknown"]
        self.system_info_label.setText(" · ".join(bits) if bits else "Connected")

    def _on_categories(self, categories: list):
        self._categories = categories
        self.sidebar.clear()
        for cat in categories:
            item = QListWidgetItem(f"{cat['title']}  ({cat['tweak_count']})")
            item.setData(Qt.UserRole, cat["id"])
            self.sidebar.addItem(item)
        if categories:
            self.sidebar.setCurrentRow(0)

    # ------------------------------------------------------------------
    # Category / tweak rendering
    # ------------------------------------------------------------------

    def _on_category_row_changed(self, current: QListWidgetItem, _previous):
        if current is None:
            return
        category_id = current.data(Qt.UserRole)
        self._current_category = category_id
        title = next((c["title"] for c in self._categories if c["id"] == category_id), category_id)
        self.category_heading.setText(title)
        self.category_subheading.setText("Loading tweaks…")
        self.apply_category_btn.setEnabled(False)
        self._clear_tweak_rows()
        self._run(self.client.tweaks, self._on_tweaks_loaded, category=category_id)

    def _clear_tweak_rows(self):
        while self.tweaks_layout.count() > 1:  # keep the trailing stretch
            item = self.tweaks_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()  # deleteLater() is deferred; hide() avoids a stale-content flash
                widget.deleteLater()

    def _on_tweaks_loaded(self, tweak_list: list):
        self._clear_tweak_rows()
        applicable = sum(1 for t in tweak_list if not t["parameters"] and not t["experimental"])
        self.category_subheading.setText(
            f"{len(tweak_list)} tweak(s) -- \u201cApply all\u201d covers {applicable} of them "
            "(the rest need a choice or a confirmation)"
        )
        self.apply_category_btn.setEnabled(applicable > 0)
        for tweak in tweak_list:
            row = self._make_tweak_row(tweak)
            self.tweaks_layout.insertWidget(self.tweaks_layout.count() - 1, row)

    def _make_tweak_row(self, tweak: dict) -> QWidget:
        frame = QFrame()
        frame.setObjectName("tweakRow")
        outer = QVBoxLayout(frame)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(6)

        top_row = QHBoxLayout()
        title = QLabel(tweak["title"])
        title.setObjectName("tweakTitle")
        title.setWordWrap(True)
        top_row.addWidget(title, 1)
        if tweak["requires_admin"]:
            badge = QLabel("ADMIN")
            badge.setProperty("class", "badgeAdmin")
            top_row.addWidget(badge, 0, Qt.AlignTop)
        if tweak["experimental"]:
            badge = QLabel("EXPERIMENTAL")
            badge.setProperty("class", "badgeExperimental")
            top_row.addWidget(badge, 0, Qt.AlignTop)
        outer.addLayout(top_row)

        description = QLabel(tweak["description"])
        description.setObjectName("tweakDescription")
        description.setWordWrap(True)
        outer.addWidget(description)

        bottom_row = QHBoxLayout()
        result_label = QLabel("")
        self._result_labels_by_tweak[tweak["id"]] = result_label
        bottom_row.addWidget(result_label, 1)

        combo = None
        if tweak["parameters"]:
            combo = QComboBox()
            combo.addItems(tweak["parameters"])
            bottom_row.addWidget(combo)

        apply_btn = QPushButton("Apply")
        apply_btn.setProperty("class", "primary")
        apply_btn.clicked.connect(lambda _checked, t=tweak, c=combo: self._on_apply_tweak_clicked(t, c))
        self._apply_buttons_by_tweak[tweak["id"]] = apply_btn
        bottom_row.addWidget(apply_btn)
        outer.addLayout(bottom_row)

        self._restyle(frame)
        return frame

    def _restyle(self, widget: QWidget):
        """Re-polish a dynamically-created widget so property-based QSS
        selectors (class=primary, class=badgeAdmin, ...) take effect --
        Qt only applies those automatically to widgets that existed when
        the stylesheet was first set."""
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        for child in widget.findChildren(QWidget):
            child.style().unpolish(child)
            child.style().polish(child)

    # ------------------------------------------------------------------
    # Applying tweaks / categories / presets
    # ------------------------------------------------------------------

    def _confirm(self, title: str, text: str) -> bool:
        return QMessageBox.question(
            self, title, text, QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        ) == QMessageBox.Yes

    def _on_apply_tweak_clicked(self, tweak: dict, combo: Optional[QComboBox]):
        param = combo.currentText() if combo is not None else None

        if tweak["experimental"]:
            if not self._confirm(
                "Experimental tweak",
                f"\u201c{tweak['title']}\u201d is experimental: {tweak['description']}\n\n"
                "Continue anyway?",
            ):
                return
        if tweak["id"] == "remove-bundled-apps":
            if not self._confirm(
                "Move apps to Trash?",
                "This moves Pages, Numbers, Keynote, iMovie, and GarageBand "
                "(whichever are installed) to the Trash. They aren't "
                "permanently deleted until you empty it.\n\nContinue?",
            ):
                return

        btn = self._apply_buttons_by_tweak.get(tweak["id"])
        if btn:
            btn.setEnabled(False)
        self._set_result_label(tweak["id"], "Applying…", "info")
        self._log(f"Applying: {tweak['title']}")

        self._run(
            self.client.apply_tweak,
            lambda result: self._on_apply_result(tweak["id"], result),
            lambda message: self._on_apply_error(tweak["id"], message),
            tweak["id"], param=param, confirm_experimental=tweak["experimental"],
        )

    def _set_result_label(self, tweak_id: str, text: str, level: str):
        label = self._result_labels_by_tweak.get(tweak_id)
        if not label:
            return
        color = {"info": "#6E6E73", "success": "#2E7D4F", "error": "#B34747"}.get(level, "#6E6E73")
        label.setStyleSheet(f"color: {color}; font-size: 11.5px;")
        label.setText(text)

    def _on_apply_result(self, tweak_id: str, result: dict):
        btn = self._apply_buttons_by_tweak.get(tweak_id)
        if btn:
            btn.setEnabled(True)
        success = result.get("success", False)
        message = result.get("message", "")
        self._set_result_label(tweak_id, message, "success" if success else "error")
        self._log(f"{tweak_id}: {message}", "success" if success else "error")

    def _on_apply_error(self, tweak_id: str, message: str):
        btn = self._apply_buttons_by_tweak.get(tweak_id)
        if btn:
            btn.setEnabled(True)
        self._set_result_label(tweak_id, message, "error")
        self._log(f"{tweak_id}: {message}", "error")

    def _on_apply_category_clicked(self):
        category_id = self._current_category
        if not category_id:
            return
        title = next((c["title"] for c in self._categories if c["id"] == category_id), category_id)
        if not self._confirm("Apply category?", f"Apply every applicable tweak in \u201c{title}\u201d?"):
            return
        self.apply_category_btn.setEnabled(False)
        self._log(f"Applying category: {title}")
        self._run(
            self.client.apply_category,
            self._on_bulk_result,
            self._on_bulk_error,
            category_id,
        )

    def _on_run_recommended_clicked(self):
        if not self._confirm(
            "Run recommended preset?",
            "This applies a handful of privacy & clutter fixes: disabling "
            "Mac analytics and personalized ads, opting out of Siri data "
            "sharing, hiding Siri Suggestions in Spotlight, and tidying up "
            "the Dock and Finder. Nothing destructive.\n\nContinue?",
        ):
            return
        self._log("Running recommended preset…")
        self._run(self.client.apply_preset, self._on_bulk_result, self._on_bulk_error, "recommended")

    def _on_run_everything_clicked(self):
        if not self._confirm(
            "Run EVERYTHING?",
            "This applies every non-parameterized tweak across every "
            "category, including the experimental Apple Intelligence "
            "toggle and moving bundled apps to the Trash.\n\n"
            "This is a lot of changes at once. Continue?",
        ):
            return
        self._log("Running EVERYTHING…")
        self._run(self.client.apply_preset, self._on_bulk_result, self._on_bulk_error, "all")

    def _on_bulk_result(self, result: dict):
        self.apply_category_btn.setEnabled(True)
        results = result.get("results", [])
        succeeded = sum(1 for r in results if r.get("success"))
        for r in results:
            self._set_result_label(r["id"], r.get("message", ""), "success" if r.get("success") else "error")
            self._log(f"{r['id']}: {r.get('message', '')}", "success" if r.get("success") else "error")
        self._log(f"Done -- {succeeded}/{len(results)} succeeded.", "success" if succeeded == len(results) else "error")

    def _on_bulk_error(self, message: str):
        self.apply_category_btn.setEnabled(True)
        self._log(message, "error")
        QMessageBox.warning(self, "That didn't work", message)

    # ------------------------------------------------------------------
    # History dialog
    # ------------------------------------------------------------------

    def _open_history_dialog(self):
        dialog = HistoryDialog(self.client, self)
        dialog.exec_()

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        if self._we_started_backend and self._backend_proc is not None:
            backend_launcher.stop_backend(self._backend_proc)
        super().closeEvent(event)
