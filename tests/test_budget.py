from decimal import Decimal
import pytest
from services.budget_service import (BudgetProfile, budget_summary, estimate_plan,
    load_profile, proportional_allocation, save_profile)
from services.finance_service import create_objective
from repositories.objective_repository import list_objectives


def test_salary_and_expenses_conversion():
    profile = BudgetProfile(income="4000000", fixed="1000000", variable="600000", reserve="200000")
    result = budget_summary(profile)
    assert result["available"] == 1100000
    fortnightly = BudgetProfile(income="2000000", frequency="fortnightly", fixed="1000000", variable="600000", reserve="200000")
    assert budget_summary(fortnightly) == result


def test_deficit_and_cents_do_not_overstate_cash():
    result = budget_summary(BudgetProfile(income="100.01", fixed="50"))
    assert result["available"] == Decimal("25.00")
    result = budget_summary(BudgetProfile(income="100", fixed="120"))
    assert result["available"] == 0
    assert result["deficit"] == 20


@pytest.mark.parametrize("profile", [BudgetProfile(income="-1"), BudgetProfile(frequency="weekly"), BudgetProfile(variable="NaN")])
def test_budget_validation(profile):
    with pytest.raises(ValueError):
        budget_summary(profile)


def test_shared_allocation_and_cents():
    assert proportional_allocation(["100", "100", "100"], "100") == [Decimal("33.34"), Decimal("33.33"), Decimal("33.33")]
    assert sum(proportional_allocation(["100", "200"], "1000")) == 300
    assert proportional_allocation(["0", "0"], "100") == [0, 0]
    assert proportional_allocation(["100", "200"], "0") == [0, 0]


def test_profile_persistence_and_entire_plan(engine):
    profile = BudgetProfile(income="1000", fixed="200")
    save_profile(engine, profile)
    assert load_profile(engine).income == "1000.00"
    create_objective(engine, "A", "debt", "1000")
    create_objective(engine, "B", "goal", "2000")
    create_objective(engine, "Excluida", "goal", "9000", included=False)
    plan = estimate_plan(profile, list_objectives(engine))
    assert plan["available"] == 400
    assert plan["required"] == 600
    assert plan["gap"] == 200
    assert plan["periods"] == 8
    assert sum(r["allocation"] for r in plan["rows"]) == 400
    assert len(plan["rows"]) == 2
    assert estimate_plan(BudgetProfile(), list_objectives(engine))["periods"] is None
    assert estimate_plan(BudgetProfile(), [])["periods"] == 0
