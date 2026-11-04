from decimal import Decimal

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QFormLayout, QFrame, QGridLayout,
    QHBoxLayout, QLayout, QMainWindow, QMessageBox, QProgressBar, QScrollArea,
    QSpinBox, QVBoxLayout, QWidget)
from sqlalchemy.exc import SQLAlchemyError

from config.settings import today
from desktop.dialogs import MovementDialog, ObjectiveDialog
from desktop.recurring_editor import RecurringEditor
from desktop.widgets import BalanceChart, amount_input, button, card, label, metric, table
from repositories.objective_repository import list_objectives
from services.budget_service import BudgetProfile, estimate_plan, load_profile, save_profile
from services.calculation_service import installment, periods_needed, remaining
from services.expense_service import expense_summary, list_expenses, set_expense_included
from services.finance_service import delete_movement, delete_objective, snapshot
from services.recurring_service import (apply_expense_baseline, expense_baseline, fixed_total, load_recurring)
from utils.currency import ZERO, cop, money


class MainWindow(QMainWindow):
    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self.section = "Resumen"
        self.setWindowTitle("Mi plan · Finanzas personales")
        self.resize(1320, 900)
        self.setMinimumSize(1050, 700)
        root = QWidget()
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(225)
        nav = QVBoxLayout(sidebar)
        nav.setContentsMargins(18, 30, 18, 25)
        nav.setSpacing(10)
        nav.addWidget(label("Mi plan", "brand"))
        nav.addWidget(label("TU ESPACIO FINANCIERO", "muted"))
        nav.addSpacing(32)
        self.navigation = {}
        group = QButtonGroup(self)
        group.setExclusive(True)
        for name in ["Resumen", "Deudas", "Metas", "Mi presupuesto", "Gastos de Gmail", "Simulador"]:
            control = button(name, lambda checked=False, section=name: self.navigate(section))
            control.setCheckable(True)
            group.addButton(control)
            nav.addWidget(control)
            self.navigation[name] = control
        nav.addStretch()
        nav.addWidget(label("Todo empieza con un plan."))
        nav.addWidget(label("En tu equipo · Pesos colombianos"))
        outer.addWidget(sidebar)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        outer.addWidget(self.scroll, 1)
        self.navigate("Resumen")
        # Update date-based projections when the day changes while the app is open.
        self.last_date = today()
        self.timer = QTimer(self)
        self.timer.setInterval(60000)
        self.timer.timeout.connect(self.refresh_day)
        self.timer.start()

    def refresh_day(self):
        if self.last_date != today():
            self.last_date = today()
            self.navigate(self.section)

    def navigate(self, section):
        self.section = section
        self.navigation[section].setChecked(True)
        self.records = list_objectives(self.engine)
        self.profile = load_profile(self.engine)
        self.recurring = load_recurring(self.engine)
        self.plan = estimate_plan(self.profile, self.records)
        content = QWidget()
        content.setObjectName("page")
        layout = QVBoxLayout(content)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        layout.setContentsMargins(32, 30, 32, 32)
        layout.setSpacing(20)
        self.body = layout
        self.body.addWidget(label(f"MI PLAN  /  {section.upper()}", "eyebrow"))
        self.scroll.takeWidget().deleteLater() if self.scroll.widget() else None
        self.scroll.setWidget(content)
        {"Resumen": self.overview, "Deudas": lambda: self.objectives_page("debt"),
         "Metas": lambda: self.objectives_page("goal"), "Mi presupuesto": self.budget_page,
         "Gastos de Gmail": self.expenses_page, "Simulador": self.simulator_page}[section]()
        self.body.addStretch()

    def heading(self, title, subtitle):
        self.body.addWidget(label(title, "title"))
        self.body.addWidget(label(subtitle, "muted"))

    def metrics(self, values, columns=3):
        grid = QGridLayout()
        grid.setSpacing(14)
        for i, (title, value, hint) in enumerate(values):
            grid.addWidget(metric(title, value, hint), i // columns, i % columns)
        self.body.addLayout(grid)

    def run_action(self, action, refresh=True):
        try:
            action()
            if refresh:
                self.navigate(self.section)
        except (ValueError, SQLAlchemyError) as error:
            QMessageBox.warning(self, "No se pudo completar", str(error))

    def overview(self):
        self.heading("Tu dinero, con dirección", "Tus compromisos y tu capacidad real, en un mismo lugar.")
        records = [(o, snapshot(o)) for o in self.records]
        total = lambda kind, field: sum((s[field] for o, s in records if o.kind == kind), ZERO)
        self.metrics([
            ("Deudas pendientes", cop(total("debt", "balance")), "Lo que falta por pagar"),
            ("Metas por alcanzar", cop(total("goal", "balance")), "Lo que quieres construir"),
            ("Disponible por quincena", cop(self.plan["available"]), "Salario menos gastos y reserva declarados"),
            ("Abonado a deudas", cop(total("debt", "paid")), "Pagos registrados"),
            ("Ahorrado en metas", cop(total("goal", "paid")), "Aportes registrados"),
            ("Tu plan por quincena", cop(self.plan["required"]) if self.plan["required"] is not None else "Revisar fechas", "Solo objetivos incluidos en el plan"),
        ])
        if self.plan["configured"] and self.plan["expenses"] == 0:
            self.body.addWidget(label("Aún no has registrado gastos. El disponible mostrado es tu ingreso antes de gastos, no una capacidad de ahorro validada. Revisa Gastos de Gmail y completa Mi presupuesto.", "warning"))
        if not self.plan["configured"]:
            message, role = "Comienza en Mi presupuesto: ingresa tu salario y tus gastos para estimar un plazo alcanzable.", "notice"
        elif self.plan["required"] is None:
            message, role = "Hay fechas vencidas o sin quincenas disponibles. Reprograma los objetivos para evaluar el plan completo.", "warning"
        elif self.plan["gap"]:
            message, role = f"Para tu plazo actual faltan {cop(self.plan['gap'])} por quincena. Revisa los objetivos incluidos o amplía sus plazos.", "warning"
        else:
            message, role = "El compromiso del plan cabe en el presupuesto que has registrado.", "notice"
        self.body.addWidget(label(message, role))
        actions = QHBoxLayout()
        actions.addWidget(button("+ Nueva deuda", lambda: self.edit_objective(kind="debt"), "primary"))
        actions.addWidget(button("+ Nueva meta", lambda: self.edit_objective(kind="goal")))
        actions.addStretch()
        actions.addWidget(button("Ajustar mi presupuesto", lambda: self.navigate("Mi presupuesto")))
        self.body.addLayout(actions)
        self.body.addWidget(label("Cada avance cuenta", "sectionTitle"))
        grid = QGridLayout()
        for i, (obj, s) in enumerate(records):
            frame, box = card()
            head = QHBoxLayout()
            head.addWidget(label(obj.name, "sectionTitle"), 1)
            head.addWidget(label("DEUDA" if obj.kind == "debt" else "META", "eyebrow"))
            box.addLayout(head)
            box.addWidget(label(f"{cop(s['paid'])} de {cop(s['total'])}", "muted"))
            progress = QProgressBar()
            progress.setRange(0, 1000)
            progress.setValue(int(s["progress"] * 1000))
            progress.setTextVisible(False)
            box.addWidget(progress)
            box.addWidget(label(f"{s['progress']:.1%} · {s['status']} · {'En el plan' if obj.included else 'Fuera del plan'}", "muted"))
            box.addWidget(button("Ver y registrar movimiento", lambda checked=False, oid=obj.id: self.open_detail(oid)))
            grid.addWidget(frame, i // 2, i % 2)
        self.body.addLayout(grid)
        chart_frame, chart_box = card()
        chart_box.addWidget(label("Distribución de tus saldos", "sectionTitle"))
        chart_box.addWidget(BalanceChart([(o.name, s["balance"]) for o, s in records]))
        self.body.addWidget(chart_frame)

    def open_detail(self, oid):
        obj = next(o for o in self.records if o.id == oid)
        self.navigate("Deudas" if obj.kind == "debt" else "Metas")
        for row, current in enumerate(self.visible_objectives):
            if current.id == oid:
                self.objective_table.selectRow(row)
                break

    def edit_objective(self, objective=None, kind="debt"):
        dialog = ObjectiveDialog(self.engine, self, objective, kind)
        if dialog.exec():
            self.navigate(self.section)

    def selected_objective(self):
        row = self.objective_table.currentRow()
        return self.visible_objectives[row] if 0 <= row < len(self.visible_objectives) else None

    def objectives_page(self, kind):
        self.heading("Tus deudas" if kind == "debt" else "Tus metas de ahorro",
                     "Selecciona un registro para consultar su historial o registrar un movimiento.")
        self.visible_objectives = [o for o in self.records if o.kind == kind]
        actions = QHBoxLayout()
        actions.addWidget(button("+ Nueva deuda" if kind == "debt" else "+ Nueva meta", lambda: self.edit_objective(kind=kind), "primary"))
        actions.addStretch()
        self.body.addLayout(actions)
        rows = []
        for obj in self.visible_objectives:
            s = snapshot(obj)
            rows.append([obj.name, cop(s["total"]), cop(s["paid"]), cop(s["balance"]),
                         cop(s["installment"]) if s["installment"] is not None else "Revisar fecha",
                         s["status"], "Sí" if obj.included else "No"])
        self.objective_table = table(["Nombre", "Objetivo", "Acumulado", "Pendiente", "Por quincena", "Estado", "En plan"], rows)
        self.objective_table.setMinimumHeight(240)
        self.body.addWidget(self.objective_table)
        self.detail = QFrame()
        self.detail_layout = QVBoxLayout(self.detail)
        self.detail_layout.setContentsMargins(0, 0, 0, 0)
        self.body.addWidget(self.detail)
        self.objective_table.itemSelectionChanged.connect(self.render_detail)
        self.objective_table.itemDoubleClicked.connect(lambda _: self.edit_objective(self.selected_objective()))
        if rows:
            self.objective_table.selectRow(0)
        else:
            self.detail_layout.addWidget(label("Crea tu primer registro para empezar.", "notice"))

    def render_detail(self):
        while self.detail_layout.count():
            item = self.detail_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        obj = self.selected_objective()
        if not obj:
            return
        self.detail_layout.addWidget(label(obj.name, "sectionTitle"))
        s = snapshot(obj)
        self.detail_layout.addWidget(label(f"Creado el {obj.created_on:%d/%m/%Y} · {s['periods']} quincenas disponibles · "
            f"Fecha objetivo: {obj.target_date.strftime('%d/%m/%Y') if obj.target_date else 'plazo manual'}", "muted"))
        actions = QWidget()
        bar = QHBoxLayout(actions)
        bar.setContentsMargins(0, 0, 0, 0)
        bar.addWidget(button("Registrar abono" if obj.kind == "debt" else "Registrar aporte", lambda: self.edit_movement(obj), "primary"))
        bar.addWidget(button("Editar registro", lambda: self.edit_objective(obj)))
        bar.addWidget(button("Eliminar registro", lambda: self.remove_objective(obj), "danger"))
        bar.addStretch()
        self.detail_layout.addWidget(actions)
        movements = list(reversed(obj.movements))
        history = table(["Fecha", "Monto", "Descripción"],
            [[m.date.strftime("%d/%m/%Y"), cop(Decimal(m.amount_cents)/100), m.description] for m in movements])
        history.horizontalHeader().setStretchLastSection(True)
        self.detail_layout.addWidget(history)
        controls = QWidget()
        bar = QHBoxLayout(controls)
        bar.setContentsMargins(0, 0, 0, 0)
        def selected():
            row = history.currentRow()
            return movements[row] if 0 <= row < len(movements) else None
        correct = button("Corregir movimiento", lambda: self.edit_movement(obj, selected()) if selected() else None)
        remove = button("Eliminar movimiento", lambda: self.remove_movement(obj, selected()) if selected() else None, "danger")
        correct.setEnabled(False)
        remove.setEnabled(False)
        history.itemSelectionChanged.connect(lambda: (correct.setEnabled(selected() is not None), remove.setEnabled(selected() is not None)))
        bar.addWidget(correct)
        bar.addWidget(remove)
        bar.addStretch()
        self.detail_layout.addWidget(controls)

    def edit_movement(self, obj, movement=None):
        if MovementDialog(self.engine, obj, self, movement).exec():
            self.open_detail(obj.id)

    def remove_objective(self, obj):
        if QMessageBox.question(self, "Eliminar registro", f"¿Eliminar {obj.name} y todos sus movimientos?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.run_action(lambda: delete_objective(self.engine, obj.id))

    def remove_movement(self, obj, movement):
        if QMessageBox.question(self, "Eliminar movimiento", "¿Eliminar el movimiento y recalcular el saldo?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.run_action(lambda: delete_movement(self.engine, obj.id, movement.id))

    def budget_page(self):
        self.heading("Un plan a la medida de tu salario", "Registra lo que recibes y lo que necesitas para vivir. El resto es tu capacidad para el plan.")
        frame, box = card()
        form = QFormLayout()
        form.setVerticalSpacing(12)
        self.income = amount_input(self.profile.income)
        self.frequency = QComboBox()
        self.frequency.addItem("Mensual", "monthly")
        self.frequency.addItem("Quincenal (dos pagos al mes)", "fortnightly")
        self.frequency.setCurrentIndex(0 if self.profile.frequency == "monthly" else 1)
        self.fixed = amount_input(max(ZERO, money(self.profile.fixed) - fixed_total(self.recurring)))
        self.variable = amount_input(self.profile.variable)
        self.reserve = amount_input(self.profile.reserve)
        for title, field in [("Salario NETO recibido COP", self.income), ("Frecuencia del salario", self.frequency),
                             ("Otros gastos fijos MENSUALES COP", self.fixed), ("Gastos variables MENSUALES COP", self.variable),
                             ("Reserva MENSUAL para imprevistos COP", self.reserve)]:
            form.addRow(title, field)
        box.addLayout(form)
        box.addWidget(label("Gastos fijos que se descuentan", "sectionTitle"))
        self.recurring_editor = RecurringEditor(self.recurring)
        box.addWidget(self.recurring_editor)
        box.addWidget(button("+ Añadir gasto fijo", lambda: self.recurring_editor.add_expense()))
        box.addWidget(label("Los fijos de esta tabla se suman a «Otros gastos fijos». Semanales: monto × 52 ÷ 12. "
            "Los cargos de Gmail usan el último importe identificado desde enero; puedes corregirlo o desactivar el gasto. "
            "ChatGPT figura como estimación si solo hay un cargo.", "muted"))
        box.addWidget(label("En gastos registra vivienda, alimentación, transporte y servicios. Los abonos de las deudas del plan se calculan aparte; evita contarlos dos veces.", "muted"))
        box.addWidget(button("Guardar presupuesto y estimar", self.save_budget, "primary"))
        self.body.addWidget(frame)
        self.budget_notice = label("Los resultados corresponden al presupuesto guardado. Completa los gastos que no aparecen en los correos.", "notice")
        self.body.addWidget(self.budget_notice)
        self.metrics([
            ("Salario neto mensual", cop(self.plan["monthly_income"]), "Dos quincenas por mes"),
            ("Gastos + reserva mensual", cop(self.plan["expenses"]), "Presupuesto declarado"),
            ("Capacidad por quincena", cop(self.plan["available"]), "Después de gastos y reserva"),
        ])
        self.body.addWidget(label(f"Descuento mensual: {cop(money(self.profile.fixed))} en fijos + "
            f"{cop(money(self.profile.variable))} en variables + {cop(money(self.profile.reserve))} de reserva. "
            "La capacidad mostrada todavía debe cubrir las deudas y las metas incluidas en el plan.", "muted"))
        if self.plan["deficit"]:
            self.body.addWidget(label(f"Tus gastos superan el ingreso en {cop(self.plan['deficit'])} al mes. No hay capacidad disponible para este plan.", "warning"))
        period_text = "Sin capacidad disponible" if self.plan["periods"] is None else f"{self.plan['periods']} quincenas"
        self.body.addWidget(label(f"Plazo conjunto estimado: {period_text}", "sectionTitle"))
        self.body.addWidget(label("Estimación sin intereses: saldo de todos los objetivos incluidos ÷ capacidad compartida. Supone ingresos y gastos constantes y que el dinero liberado se reasigna. No garantiza cumplir las fechas individuales.", "muted"))
        rows = [[r["objective"].name, cop(r["snapshot"]["balance"]),
                 cop(r["snapshot"]["installment"]) if r["snapshot"]["installment"] is not None else "Revisar fecha",
                 cop(r["allocation"]), "Sí" if r["covered"] else "Requiere ajuste"] for r in self.plan["rows"]]
        self.body.addWidget(table(["Objetivo incluido", "Pendiente", "Requerido / quincena", "Reparto proporcional", "¿Cubre su cuota?"], rows))
        self.body.addWidget(label("El reparto es un escenario proporcional a los saldos, usa un único presupuesto y no registra pagos. Un objetivo grande puede absorber la mayor parte: exclúyelo del plan si quieres concentrarte en otros.", "muted"))

    def save_budget(self):
        def save():
            recurring = self.recurring_editor.expenses()
            profile = BudgetProfile(income=self.income.text(), frequency=self.frequency.currentData(),
                fixed=str(money(self.fixed.text()) + fixed_total(recurring)),
                variable=self.variable.text(), reserve=self.reserve.text())
            save_profile(self.engine, profile, recurring=recurring)
        self.run_action(save)

    def expenses_page(self):
        self.heading("Tus gastos, con contexto", "Revisión local de alertas de Gmail · 1 de enero a 20 de octubre de 2026")
        expenses = list_expenses(self.engine)
        summary = expense_summary(expenses)
        self.metrics([
            ("Gasto identificado ene–sep", cop(summary["completed_total"]), "Solo movimientos incluidos"),
            ("Promedio mensual observado", cop(summary["monthly_average"]), "Nueve meses completos"),
            ("Octubre parcial", cop(summary["months"]["2026-10"]), "Se excluye del promedio"),
        ])
        self.body.addWidget(label("Cobertura parcial: se identificaron alertas de Bancolombia. Los extractos de Nu no se pudieron leer. Efectivo y transferencias quedan fuera hasta que los clasifiques; también pueden faltar vivienda y otros gastos. Revisa esta base antes de estimar tu capacidad real.", "warning"))
        baseline = expense_baseline(expenses, existing=self.recurring)
        extra_fixed = max(ZERO, money(self.profile.fixed) - fixed_total(self.recurring))
        scenario_fixed = fixed_total(baseline["recurring"]) + extra_fixed
        scenario = estimate_plan(BudgetProfile(income=self.profile.income, frequency=self.profile.frequency,
            fixed=str(scenario_fixed), variable=str(baseline["variable"]), reserve=self.profile.reserve), self.records)
        self.body.addWidget(label(f"Escenario preliminar con tu salario: {cop(scenario['available'])} por quincena "
            "después de los gastos observados y tu reserva. Aún debes restar los gastos ausentes. "
            "Esta vista no cambia el presupuesto guardado.", "notice"))
        if summary["missing_months"]:
            self.body.addWidget(label("Meses sin gastos identificados: " + ", ".join(summary["missing_months"]) + ". El promedio no representa cobertura completa.", "warning"))
        month_table = table(["Mes", "Gasto incluido", "Movimientos"], [[m + (" · parcial" if m == "2026-10" else ""), cop(v), summary["counts"][m]] for m,v in summary["months"].items()])
        month_table.setMinimumHeight(260)
        self.body.addWidget(month_table)
        actions = QHBoxLayout()
        actions.addWidget(button("Aplicar gastos fijos y variables desde enero", self.apply_expense_average, "primary"))
        actions.addStretch()
        self.body.addLayout(actions)
        self.body.addWidget(label("Detalle revisable", "sectionTitle"))
        self.body.addWidget(label("Selecciona un movimiento para incluirlo o excluirlo. Las categorías se infieren del comercio y son orientativas. Los movimientos propios, retiros y transferencias comienzan excluidos; no se crean deudas ni abonos a partir de ellos.", "muted"))
        evidence = table(["Fecha / comercio", "Monto", "Categoría sugerida", "Tipo", "En promedio"],
            [[f"{e.date:%d/%m/%Y} · {e.merchant}", cop(Decimal(e.amount_cents)/100), e.category, e.kind, "Sí" if e.included else "No"] for e in expenses])
        evidence.setMinimumHeight(340)
        self.body.addWidget(evidence)
        bar = QHBoxLayout()
        toggle = button("Incluir / excluir seleccionado", lambda: self.run_action(lambda: set_expense_included(
            self.engine, expenses[evidence.currentRow()].id, not expenses[evidence.currentRow()].included)) if evidence.currentRow() >= 0 else None)
        source = button("Ver correo de origen", lambda: QDesktopServices.openUrl(QUrl(expenses[evidence.currentRow()].source_url)) if evidence.currentRow() >= 0 else None)
        toggle.setEnabled(False)
        source.setEnabled(False)
        evidence.itemSelectionChanged.connect(lambda: (toggle.setEnabled(evidence.currentRow() >= 0), source.setEnabled(evidence.currentRow() >= 0)))
        bar.addWidget(toggle)
        bar.addWidget(source)
        bar.addStretch()
        self.body.addLayout(bar)

    def apply_expense_average(self):
        baseline = expense_baseline(list_expenses(self.engine), existing=self.recurring)
        extra_fixed = max(ZERO, money(self.profile.fixed) - fixed_total(self.recurring))
        text = (f"Se actualizarán los gastos de Gmail desde el 1 de enero del año actual: "
                f"{cop(fixed_total(baseline['recurring']) + extra_fixed)} en fijos mensuales y "
                f"{cop(baseline['variable'])} en variables mensuales, excluyendo de estos últimos las suscripciones. "
                "Se conservan los fijos manuales, el salario y la reserva. "
                "Los importes detectados de suscripciones reemplazan sus valores anteriores. ¿Aplicar?")
        if QMessageBox.question(self, "Aplicar base de gastos", text, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.run_action(lambda: apply_expense_baseline(self.engine), refresh=False)
            self.navigate("Mi presupuesto")

    def simulator_page(self):
        self.heading("Explora tus posibilidades", "Compara plazos y abonos hipotéticos antes de tomar una decisión.")
        frame, box = card()
        form = QFormLayout()
        self.sim_choice = QComboBox()
        self.sim_choice.addItem("Escenario libre", None)
        for obj in self.records:
            self.sim_choice.addItem(obj.name, obj.id)
        self.sim_balance = amount_input("70000000")
        self.sim_extra = amount_input("0")
        self.sim_periods = QSpinBox()
        self.sim_periods.setRange(1, 100000)
        self.sim_periods.setValue(5)
        self.sim_capacity = amount_input(self.plan["available"])
        def choose():
            oid = self.sim_choice.currentData()
            obj = next((o for o in self.records if o.id == oid), None)
            self.sim_balance.setText(str(snapshot(obj)["balance"]) if obj else "70000000")
            self.sim_periods.setValue(obj.periods if obj else 5)
        self.sim_choice.currentIndexChanged.connect(choose)
        for title, field in [("Punto de partida", self.sim_choice), ("Saldo / objetivo COP", self.sim_balance),
                             ("Abono adicional COP", self.sim_extra), ("Quincenas del escenario", self.sim_periods),
                             ("Capacidad por quincena COP", self.sim_capacity)]:
            form.addRow(title, field)
        box.addLayout(form)
        box.addWidget(label("La capacidad inicia con tu presupuesto. En este escenario se dedica completa a un solo objetivo; no es simultánea con otras metas.", "muted"))
        box.addWidget(button("Calcular escenario", self.calculate_simulation, "primary"))
        self.body.addWidget(frame)
        self.sim_result = label("Elige un objetivo o crea un escenario libre. Ningún cálculo modifica tus saldos.", "notice")
        self.body.addWidget(self.sim_result)

    def calculate_simulation(self):
        try:
            balance = remaining(self.sim_balance.text(), self.sim_extra.text())
            required = installment(balance, self.sim_periods.value())
            capacity = money(self.sim_capacity.text())
            periods = periods_needed(balance, capacity) if capacity else (0 if balance == 0 else None)
            self.sim_result.setText(f"Saldo tras el abono: {cop(balance)}\n"
                f"Necesitas {cop(required)} por quincena para el plazo elegido.\n"
                + (f"Con tu capacidad tardarías {periods} quincenas (aprox. {Decimal(periods)/2} meses)." if periods is not None else "Sin capacidad disponible no hay un plazo alcanzable."))
        except ValueError as error:
            QMessageBox.warning(self, "Revisa el escenario", str(error))
