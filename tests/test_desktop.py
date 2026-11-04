import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from desktop.dialogs import MovementDialog, ObjectiveDialog
from desktop.main_window import MainWindow
from desktop.theme import STYLESHEET
from repositories.objective_repository import list_objectives
from services.finance_service import seed_examples, snapshot


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(STYLESHEET)
    yield app
    # Destroy Qt windows before Python finalizes wrappers and signal closures.
    for widget in app.topLevelWidgets():
        widget.close()
        widget.deleteLater()
    from PySide6.QtCore import QCoreApplication, QEvent
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    app.shutdown()


def test_desktop_navigation_budget_and_simulation(qt_app, engine):
    seed_examples(engine)
    window = MainWindow(engine)
    for section in window.navigation:
        QTest.mouseClick(window.navigation[section], Qt.MouseButton.LeftButton)
        assert window.section == section
    window.sim_balance.setText("1000000")
    window.sim_capacity.setText("300000")
    window.calculate_simulation()
    assert "4 quincenas" in window.sim_result.text()
    window.navigate("Mi presupuesto")
    window.income.setText("4000000")
    window.fixed.setText("1000000")
    window.variable.setText("600000")
    window.reserve.setText("200000")
    window.save_budget()
    assert window.plan["available"] == 1100000
    window.navigate("Deudas")
    assert window.objective_table.rowCount() == 4
    window.close()


def test_desktop_create_pay_and_correct(qt_app, engine):
    dialog = ObjectiveDialog(engine)
    dialog.name.setText("Deuda desde escritorio")
    dialog.total.setText("1000")
    dialog.save()
    obj = list_objectives(engine)[0]
    payment = MovementDialog(engine, obj)
    payment.amount.setText("250")
    payment.save()
    obj = list_objectives(engine)[0]
    assert snapshot(obj)["balance"] == 750
    correction = MovementDialog(engine, obj, movement=obj.movements[0])
    correction.amount.setText("500")
    correction.save()
    window = MainWindow(engine)
    window.navigate("Deudas")
    assert window.objective_table.item(0, 3).text() == "$ 500 COP"
    window.close()


def test_fixed_expenses_are_saved_and_deducted_once(qt_app, engine):
    from services.budget_service import BudgetProfile, load_profile, save_profile
    from services.recurring_service import RecurringExpense, load_recurring
    parking = RecurringExpense("parking", "Parqueadero", "18000", frequency="weekly")
    spotify = RecurringExpense("spotify", "Spotify", "18500")
    save_profile(engine, BudgetProfile(income="4000000", fixed="96500", variable="1000000"), recurring=[parking, spotify])
    window = MainWindow(engine)
    window.navigate("Mi presupuesto")
    assert window.fixed.text() == "0.00"
    assert window.recurring_editor.item(0, 4).text() == "$ 78.000 COP"
    window.save_budget()
    assert window.plan["available"] == 1451750
    assert load_profile(engine).fixed == "96500.00"
    window.recurring_editor.cellWidget(1, 0).setChecked(False)
    window.save_budget()
    assert window.plan["available"] == 1461000
    assert not load_recurring(engine)[1].enabled
    window.close()
