from datetime import date
from decimal import Decimal
from types import SimpleNamespace
import pytest

from services.budget_service import BudgetProfile, budget_summary, load_profile, save_profile
from services.expense_service import import_evidence
from services.recurring_service import (RecurringExpense, apply_expense_baseline, expense_baseline,
                                        fixed_total, load_recurring, monthly_cost)


def observation(id, when, merchant, cents, included=True):
    return SimpleNamespace(id=id, date=when, merchant=merchant, amount_cents=cents, included=included)


def test_weekly_parking_uses_annual_average():
    parking = RecurringExpense("parking", "Parqueadero", "18000", frequency="weekly")
    assert monthly_cost(parking) == Decimal("78000.00")
    assert monthly_cost(RecurringExpense("x", "Pequeño", "1", frequency="weekly")) == Decimal("4.34")
    assert monthly_cost(RecurringExpense("x", "Desactivado", "18000", enabled=False)) == 0
    assert budget_summary(BudgetProfile(income="4000000", fixed=str(monthly_cost(parking))))["available"] == 1961000


def test_baseline_uses_january_onward_and_does_not_double_count():
    rows = [observation(1, date(2025, 12, 15), "Spotify", 999999),
            observation(2, date(2026, 1, 7), "SPOTIFY", 1010000),
            observation(3, date(2026, 9, 7), "Spotify", 1850000),
            observation(4, date(2026, 10, 7), "Spotify", 1850000),
            observation(5, date(2026, 11, 7), "Spotify", 99999999),
            observation(6, date(2026, 1, 8), "Comida", 10000),
            observation(7, date(2026, 9, 8), "Mercado", 20000),
            observation(8, date(2026, 10, 8), "Comida", 999999),
            observation(9, date(2026, 9, 9), "Compra excluida", 999999, False)]
    parking = RecurringExpense("parking", "Parqueadero", "18000", frequency="weekly")
    result = expense_baseline(rows, as_of=date(2026, 10, 20), existing=[parking])
    assert result["variable_sum"] == 300
    assert result["variable"] == Decimal("33.34")
    assert result["months"] == 9
    assert fixed_total(result["recurring"]) == 96500
    assert next(r for r in result["recurring"] if r.key == "spotify").amount == "18500"


def test_january_has_no_complete_month_and_single_charge_is_estimated():
    result = expense_baseline([observation(1, date(2026, 1, 5), "GOOGLE ChatGPT", 8100000)], as_of=date(2026, 1, 15))
    assert result["variable"] == 0
    assert "recurrencia estimada" in result["recurring"][0].source


def test_persistent_baseline_preserves_manual_costs_salary_and_reserve(engine):
    parking = RecurringExpense("parking", "Parqueadero", "18000", frequency="weekly")
    save_profile(engine, BudgetProfile(income="4000000", fixed="79000", reserve="10000"), recurring=[parking])
    import_evidence(engine, [dict(id="spotify", email_ts="2026-09-07T17:00:00+00:00",
        snippet="Bancolombia: Compraste $18.500,00 en Spotify con tu T.Deb *1234, el 07/09/2026 a las 12:00.")])
    for _ in range(2):
        apply_expense_baseline(engine, as_of=date(2026, 10, 20))
        saved = load_profile(engine)
        assert saved.fixed == "97500.00"  # 78,000 parking + 18,500 Spotify + 1,000 manual.
        assert saved.variable == "0.00"
        assert saved.income == "4000000.00" and saved.reserve == "10000.00"
        assert len(load_recurring(engine)) == 2


def test_recurring_validation_rolls_back_profile(engine):
    save_profile(engine, BudgetProfile(income="1000"))
    with pytest.raises(ValueError):
        save_profile(engine, BudgetProfile(income="2000"), recurring=[RecurringExpense("x", "Spotify", "-1")])
    assert load_profile(engine).income == "1000.00"
    assert load_recurring(engine) == []
    with pytest.raises(ValueError):
        fixed_total([RecurringExpense("x", "A", "1"), RecurringExpense("x", "B", "2")])
