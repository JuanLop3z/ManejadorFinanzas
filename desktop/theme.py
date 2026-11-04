import os
from pathlib import Path
from PySide6.QtGui import QFont, QFontDatabase


def apply_theme(app):
    # Offscreen Qt on Windows also needs explicit fonts for faithful previews.
    fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    for name in ("segoeui.ttf", "segoeuib.ttf"):
        path = fonts / name
        if path.exists():
            QFontDatabase.addApplicationFont(str(path))
    app.setFont(QFont("Segoe UI", 10))
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)


STYLESHEET = """
QWidget { color: #1c3044; font-family: 'Segoe UI'; font-size: 13px; }
QMainWindow, QDialog { background: #f5f7fb; }
QWidget#page { background: #f5f7fb; }
QFrame#sidebar { background: #142d3e; border: none; }
QFrame#sidebar QLabel { color: #c6d5df; }
QFrame#sidebar QLabel#brand { color: white; font-size: 28px; font-weight: 700; }
QFrame#sidebar QPushButton { background: transparent; color: #cfdae2; text-align: left;
    border: none; padding: 13px 18px; border-radius: 8px; font-size: 14px; }
QFrame#sidebar QPushButton:hover { background: #244455; }
QFrame#sidebar QPushButton:checked { background: #167d83; color: white; font-weight: 600; }
QLabel#title { font-size: 28px; font-weight: 700; color: #152f42; }
QLabel#sectionTitle { font-size: 17px; font-weight: 600; }
QLabel#muted { color: #61778a; }
QLabel#eyebrow { color: #0b8c86; font-size: 11px; font-weight: 700; }
QFrame#card { background: white; border: 1px solid #e2e9f0; border-radius: 12px; }
QLabel#metricValue { font-size: 23px; font-weight: 700; color: #163d50; }
QLabel#notice { background: #e7f4f0; color: #16685d; padding: 14px; border-radius: 8px; }
QLabel#warning { background: #fff2de; color: #865417; padding: 14px; border-radius: 8px; }
QPushButton { background: white; border: 1px solid #d7e2ea; border-radius: 7px;
    padding: 9px 14px; font-weight: 600; }
QPushButton:hover { background: #eaf3f4; border-color: #57a9aa; }
QPushButton#primary { background: #09857e; border-color: #09857e; color: white; }
QPushButton#primary:hover { background: #076c66; }
QPushButton#danger { color: #bd4051; }
QPushButton:disabled { color: #9baab5; background: #eef1f4; }
QLineEdit, QSpinBox, QComboBox, QDateEdit { background: white; border: 1px solid #d5e0e8;
    border-radius: 6px; padding: 8px; min-height: 20px; selection-background-color: #09857e; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus { border: 1px solid #09857e; }
QTableWidget { background: white; border: 1px solid #e2e9f0; border-radius: 8px;
    gridline-color: #edf1f5; alternate-background-color: #f8fafc; selection-background-color: #d9eeec;
    selection-color: #123f42; }
QTableWidget::item { padding: 9px; }
QHeaderView::section { background: #edf2f6; border: none; border-bottom: 1px solid #dfe6ed;
    padding: 12px 9px; color: #4e6477; font-weight: 600; }
QProgressBar { border: none; background: #e8eff3; border-radius: 4px; height: 8px; max-height: 8px; }
QProgressBar::chunk { background: #12a395; border-radius: 4px; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: #f0f3f6; width: 9px; border: none; }
QScrollBar::handle:vertical { background: #c9d6df; min-height: 30px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QTabWidget::pane { border: none; }
QTabBar::tab { padding: 10px 20px; background: #edf2f5; }
QTabBar::tab:selected { color: #087e77; background: white; }
QToolTip { background: #142d3e; color: white; padding: 7px; border: none; }
"""
