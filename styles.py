"""
QSS for deblaot's GUI.

Design intent: this is a system-utility for macOS, so it should feel like
one -- a light neutral gray (the same #F5F5F7 System Settings and Finder's
sidebar use), one deliberate accent color reserved for primary actions and
selection state, flat panels with hairline dividers instead of drop-shadow
cards, and the system font left alone rather than substituted for something
that would look imported. Color is used to mean something (admin required,
experimental, success, error) rather than to decorate.
"""

BG = "#F5F5F7"
SIDEBAR_BG = "#E8E8EC"
SIDEBAR_HOVER = "#DCDCE2"
DIVIDER = "#D8D8DC"
TEXT_PRIMARY = "#1D1D1F"
TEXT_SECONDARY = "#6E6E73"
ACCENT = "#3B5BA5"
ACCENT_HOVER = "#31498A"
ACCENT_PRESSED = "#283C73"
ADMIN_BG = "#F5E8D0"
ADMIN_FG = "#7A5A1E"
EXPERIMENTAL_BG = "#F5DEDE"
EXPERIMENTAL_FG = "#8A3A3A"
DANGER = "#B34747"
DANGER_HOVER = "#9A3A3A"
SUCCESS = "#2E7D4F"

STYLESHEET = f"""
QMainWindow {{
    background-color: {BG};
}}

QWidget#centralWidget, QWidget#detailPane, QWidget#tweaksContainer {{
    background-color: {BG};
}}

/* ---------- header ---------- */
QWidget#headerBar {{
    background-color: {BG};
    border-bottom: 1px solid {DIVIDER};
}}
QLabel#appTitle {{
    color: {TEXT_PRIMARY};
    font-size: 18px;
    font-weight: 600;
}}
QLabel#systemInfo {{
    color: {TEXT_SECONDARY};
    font-size: 12px;
}}
QLabel#statusLabel {{
    color: {TEXT_SECONDARY};
    font-size: 12px;
}}

/* ---------- sidebar ---------- */
QListWidget#sidebar {{
    background-color: {SIDEBAR_BG};
    border: none;
    outline: 0;
    padding: 10px 0px;
    font-size: 13px;
}}
QListWidget#sidebar::item {{
    color: {TEXT_PRIMARY};
    padding: 9px 14px;
    margin: 1px 8px;
    border-radius: 6px;
}}
QListWidget#sidebar::item:selected {{
    background-color: {ACCENT};
    color: white;
}}
QListWidget#sidebar::item:hover:!selected {{
    background-color: {SIDEBAR_HOVER};
}}

QWidget#sidebarActions {{
    background-color: {SIDEBAR_BG};
    border-top: 1px solid {DIVIDER};
}}

/* ---------- tweak rows ---------- */
QFrame#tweakRow {{
    background-color: white;
    border: 1px solid {DIVIDER};
    border-radius: 8px;
}}
QLabel#tweakTitle {{
    color: {TEXT_PRIMARY};
    font-size: 13px;
    font-weight: 600;
}}
QLabel#tweakDescription {{
    color: {TEXT_SECONDARY};
    font-size: 12px;
}}
QLabel#categoryHeading {{
    color: {TEXT_PRIMARY};
    font-size: 20px;
    font-weight: 600;
}}
QLabel#categorySubheading {{
    color: {TEXT_SECONDARY};
    font-size: 13px;
}}

QLabel.badgeAdmin {{
    background-color: {ADMIN_BG};
    color: {ADMIN_FG};
    font-size: 10px;
    font-weight: 600;
    border-radius: 4px;
    padding: 2px 6px;
}}
QLabel.badgeExperimental {{
    background-color: {EXPERIMENTAL_BG};
    color: {EXPERIMENTAL_FG};
    font-size: 10px;
    font-weight: 600;
    border-radius: 4px;
    padding: 2px 6px;
}}

/* ---------- buttons ---------- */
QPushButton {{
    background-color: #EFEFF2;
    color: {TEXT_PRIMARY};
    border: 1px solid {DIVIDER};
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 12px;
}}
QPushButton:hover {{
    background-color: #E4E4E8;
}}
QPushButton:pressed {{
    background-color: #D8D8DC;
}}
QPushButton:disabled {{
    color: #B0B0B4;
    background-color: #F0F0F2;
}}

QPushButton.primary {{
    background-color: {ACCENT};
    color: white;
    border: none;
    font-weight: 600;
}}
QPushButton.primary:hover {{
    background-color: {ACCENT_HOVER};
}}
QPushButton.primary:pressed {{
    background-color: {ACCENT_PRESSED};
}}
QPushButton.primary:disabled {{
    background-color: #A9B7D6;
    color: #EFEFF2;
}}

QPushButton.danger {{
    background-color: white;
    color: {DANGER};
    border: 1px solid {DANGER};
}}
QPushButton.danger:hover {{
    background-color: {DANGER};
    color: white;
}}

QComboBox {{
    border: 1px solid {DIVIDER};
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 12px;
    background-color: white;
    min-width: 100px;
}}

/* ---------- log console ---------- */
QPlainTextEdit#logConsole {{
    background-color: #1D1D1F;
    color: #E4E4E8;
    border: none;
    font-family: "SF Mono", Menlo, Consolas, monospace;
    font-size: 11.5px;
    padding: 8px;
}}
QWidget#logBar {{
    background-color: {BG};
    border-top: 1px solid {DIVIDER};
}}
QLabel#logBarTitle {{
    color: {TEXT_SECONDARY};
    font-size: 11px;
    font-weight: 600;
}}

/* ---------- history dialog ---------- */
QTableWidget {{
    background-color: white;
    gridline-color: {DIVIDER};
    border: 1px solid {DIVIDER};
    font-size: 12px;
}}
QHeaderView::section {{
    background-color: {SIDEBAR_BG};
    color: {TEXT_SECONDARY};
    padding: 6px;
    border: none;
    border-bottom: 1px solid {DIVIDER};
    font-size: 11px;
    font-weight: 600;
}}

QScrollArea {{
    border: none;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
}}
QScrollBar::handle:vertical {{
    background: #C6C6CB;
    border-radius: 5px;
    min-height: 24px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
"""
