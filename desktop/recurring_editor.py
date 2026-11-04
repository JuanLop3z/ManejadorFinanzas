from dataclasses import replace
from uuid import uuid4

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QComboBox, QHeaderView, QLineEdit, QTableWidget, QTableWidgetItem

from desktop.widgets import amount_input
from services.recurring_service import RecurringExpense, monthly_cost
from utils.currency import cop


class RecurringEditor(QTableWidget):
    def __init__(self, expenses, parent=None):
        super().__init__(0, 6, parent)
        self.setHorizontalHeaderLabels(["Activo", "Gasto fijo", "Monto COP", "Frecuencia", "Equivalente mensual", "Origen / referencia"])
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(48)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setStretchLastSection(True)
        self.setMinimumHeight(200)
        self.metadata = []
        for expense in expenses:
            self.add_expense(expense)

    def add_expense(self, expense=None):
        expense = expense or RecurringExpense(str(uuid4()), "Nuevo gasto", "0")
        row = self.rowCount()
        self.insertRow(row)
        self.metadata.append(expense)
        enabled = QCheckBox()
        enabled.setChecked(expense.enabled)
        self.setCellWidget(row, 0, enabled)
        self.setCellWidget(row, 1, QLineEdit(expense.name))
        amount = amount_input(expense.amount)
        self.setCellWidget(row, 2, amount)
        frequency = QComboBox()
        frequency.setMinimumWidth(110)
        frequency.addItem("Mensual", "monthly")
        frequency.addItem("Semanal", "weekly")
        frequency.setCurrentIndex(1 if expense.frequency == "weekly" else 0)
        self.setCellWidget(row, 3, frequency)
        for column, value in [(4, ""), (5, expense.source)]:
            item = QTableWidgetItem(value)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item.setToolTip(expense.source)
            self.setItem(row, column, item)
        amount.textChanged.connect(lambda: self.update_monthly(row))
        self.cellWidget(row, 1).textChanged.connect(lambda: self.update_monthly(row))
        frequency.currentIndexChanged.connect(lambda: self.update_monthly(row))
        enabled.toggled.connect(lambda: self.update_monthly(row))
        self.update_monthly(row)

    def expense_at(self, row):
        return replace(self.metadata[row], name=self.cellWidget(row, 1).text(),
                       amount=self.cellWidget(row, 2).text(), frequency=self.cellWidget(row, 3).currentData(),
                       enabled=self.cellWidget(row, 0).isChecked())

    def expenses(self):
        return [self.expense_at(row) for row in range(self.rowCount())]

    def update_monthly(self, row):
        try:
            self.item(row, 4).setText(cop(monthly_cost(self.expense_at(row))))
        except ValueError:
            self.item(row, 4).setText("Revisa el monto o nombre")
