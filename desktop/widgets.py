from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QAbstractItemView, QFrame, QHeaderView, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)


def label(text, role=None):
    widget = QLabel(str(text))
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setWordWrap(True)
    if role:
        widget.setObjectName(role)
    return widget


def button(text, callback, role=None):
    widget = QPushButton(text)
    if role:
        widget.setObjectName(role)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    widget.clicked.connect(callback)
    return widget


def card():
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(20, 17, 20, 17)
    layout.setSpacing(9)
    return frame, layout


def metric(title, value, hint=""):
    frame, layout = card()
    layout.addWidget(label(title, "muted"))
    layout.addWidget(label(value, "metricValue"))
    if hint:
        layout.addWidget(label(hint, "muted"))
    return frame


def amount_input(value="0"):
    widget = QLineEdit(str(value))
    widget.setPlaceholderText("Ej. 4000000")
    widget.setToolTip("COP sin separadores de miles; punto para decimales.")
    widget.setMaxLength(20)
    return widget


def table(headers, rows):
    widget = QTableWidget(len(rows), len(headers))
    widget.setHorizontalHeaderLabels(headers)
    widget.setAlternatingRowColors(True)
    widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    widget.verticalHeader().setVisible(False)
    widget.verticalHeader().setDefaultSectionSize(46)
    for i, row in enumerate(rows):
        for j, value in enumerate(row):
            widget.setItem(i, j, QTableWidgetItem(str(value)))
    widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    widget.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    widget.setMinimumHeight(180)
    return widget


class BalanceChart(QWidget):
    COLORS = ["#0d9488", "#3b82f6", "#f59e0b", "#8b5cf6", "#f472b6", "#38bdf8", "#64748b"]

    def __init__(self, balances, parent=None):
        super().__init__(parent)
        self.balances = [(name, value) for name, value in balances if value > 0]
        self.setMinimumHeight(max(220, len(self.balances) * 28 + 25))
        self.setToolTip("Distribución de todos los saldos pendientes, incluidos los objetivos fuera del plan.")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        total = sum(value for _, value in self.balances)
        rect = QRectF(22, 18, 170, 170)
        painter.setPen(QPen(QColor("#e5edf2"), 23))
        painter.drawEllipse(rect)
        angle = 90 * 16
        for i, (name, value) in enumerate(self.balances):
            color = QColor(self.COLORS[i % len(self.COLORS)])
            span = -int(value / total * 360 * 16)
            painter.setPen(QPen(color, 23))
            painter.drawArc(rect, angle, span)
            angle += span
            y = 23 + i * 28
            painter.fillRect(230, y, 10, 10, color)
            painter.setPen(QColor("#304d60"))
            painter.drawText(252, y + 11, f"{name}  ·  {value / total:.1%}")
        painter.setPen(QColor("#163d50"))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Saldos\npendientes" if total else "Sin saldos\npendientes")
