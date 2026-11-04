from datetime import date
from decimal import Decimal
from uuid import uuid4
from PySide6.QtCore import QDate
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDateEdit, QDialog, QFormLayout,
    QHBoxLayout, QLineEdit, QMessageBox, QSpinBox, QVBoxLayout)
from sqlalchemy.exc import SQLAlchemyError
from config.settings import today
from desktop.widgets import amount_input, button, label
from services.finance_service import create_objective, save_movement, snapshot, update_objectives


def python_date(widget):
    value = widget.date()
    return date(value.year(), value.month(), value.day())


class FinancialDialog(QDialog):
    def attempt(self, action):
        try:
            action()
            self.accept()
        except (ValueError, SQLAlchemyError) as error:
            QMessageBox.warning(self, "Revisa los datos", str(error))


class ObjectiveDialog(FinancialDialog):
    def __init__(self, engine, parent=None, objective=None, kind="debt"):
        super().__init__(parent)
        self.engine, self.objective = engine, objective
        self.setWindowTitle("Editar registro" if objective else "Nuevo objetivo financiero")
        self.setMinimumWidth(490)
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 24, 26, 24)
        root.addWidget(label(self.windowTitle(), "sectionTitle"))
        form = QFormLayout()
        form.setVerticalSpacing(14)
        self.name = QLineEdit(objective.name if objective else "")
        self.name.setMaxLength(120)
        self.kind = QComboBox()
        self.kind.addItem("Deuda", "debt")
        self.kind.addItem("Meta de ahorro", "goal")
        self.kind.setCurrentIndex(0 if (objective.kind if objective else kind) == "debt" else 1)
        self.total = amount_input(snapshot(objective)["total"] if objective else "")
        self.periods = QSpinBox()
        self.periods.setRange(1, 100000)
        self.periods.setValue(objective.periods if objective else 5)
        self.use_date = QCheckBox("Usar una fecha objetivo")
        self.use_date.setChecked(bool(objective and objective.target_date))
        self.target = QDateEdit()
        self.target.setCalendarPopup(True)
        self.target.setDisplayFormat("dd/MM/yyyy")
        self.target.setDate(QDate(objective.target_date or today()) if objective else QDate(today()))
        self.target.setEnabled(self.use_date.isChecked())
        self.use_date.toggled.connect(self.target.setEnabled)
        self.included = QCheckBox("Incluir en mi planificación")
        self.included.setChecked(objective.included if objective else True)
        for title, field in [("Nombre", self.name), ("Tipo", self.kind), ("Valor objetivo COP", self.total),
                             ("Quincenas manuales", self.periods), ("", self.use_date),
                             ("Fecha objetivo", self.target), ("", self.included)]:
            form.addRow(title, field)
        root.addLayout(form)
        root.addWidget(label("Con fecha se cuentan el día 15 y fin de mes. Sin fecha se usa el plazo manual.", "muted"))
        actions = QHBoxLayout()
        actions.addStretch()
        actions.addWidget(button("Cancelar", self.reject))
        actions.addWidget(button("Guardar registro", lambda: self.attempt(self.save), "primary"))
        root.addLayout(actions)

    def save(self):
        values = dict(name=self.name.text(), kind=self.kind.currentData(), total=self.total.text(),
                      periods=self.periods.value(), target_date=python_date(self.target) if self.use_date.isChecked() else None,
                      included=self.included.isChecked())
        if self.objective:
            update_objectives(self.engine, [dict(id=self.objective.id, **values)])
        else:
            create_objective(self.engine, **values)


class MovementDialog(FinancialDialog):
    def __init__(self, engine, objective, parent=None, movement=None):
        super().__init__(parent)
        self.engine, self.objective, self.movement = engine, objective, movement
        self.request_id = str(uuid4())
        self.setWindowTitle("Corregir movimiento" if movement else "Registrar abono" if objective.kind == "debt" else "Registrar aporte")
        self.setMinimumWidth(470)
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 24, 26, 24)
        root.addWidget(label(self.windowTitle(), "sectionTitle"))
        root.addWidget(label(objective.name, "muted"))
        form = QFormLayout()
        form.setVerticalSpacing(14)
        self.amount = amount_input(Decimal(movement.amount_cents)/100 if movement else "")
        self.date = QDateEdit(QDate(movement.date if movement else today()))
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("dd/MM/yyyy")
        self.date.setMaximumDate(QDate(today()))
        self.description = QLineEdit(movement.description if movement else "")
        self.description.setMaxLength(500)
        form.addRow("Monto COP", self.amount)
        form.addRow("Fecha", self.date)
        form.addRow("Descripción", self.description)
        root.addLayout(form)
        actions = QHBoxLayout()
        actions.addStretch()
        actions.addWidget(button("Cancelar", self.reject))
        actions.addWidget(button("Guardar movimiento", lambda: self.attempt(self.save), "primary"))
        root.addLayout(actions)

    def save(self):
        save_movement(self.engine, self.objective.id, self.amount.text(), python_date(self.date),
                      self.description.text(), request_id=self.request_id,
                      movement_id=self.movement.id if self.movement else None)
