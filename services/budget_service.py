"""Salary-based estimates, with one shared budget for the entire plan."""
import json
from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_DOWN
from sqlalchemy.orm import Session
from database.connection import transaction
from database.models import Setting
from services.calculation_service import periods_needed
from services.finance_service import snapshot
from utils.currency import CENT, ZERO, money


@dataclass(frozen=True)
class BudgetProfile:
    income: str = "0"
    frequency: str = "monthly"
    fixed: str = "0"
    variable: str = "0"
    reserve: str = "0"


def budget_summary(profile):
    if profile.frequency not in ("monthly", "fortnightly"):
        raise ValueError("Selecciona salario mensual o quincenal.")
    income = money(profile.income)
    monthly_income = income * (2 if profile.frequency == "fortnightly" else 1)
    expenses = money(profile.fixed) + money(profile.variable) + money(profile.reserve)
    net = monthly_income - expenses
    return dict(monthly_income=monthly_income, expenses=expenses,
                fortnightly_income=(monthly_income / 2).quantize(CENT, rounding=ROUND_DOWN),
                available=(max(ZERO, net) / 2).quantize(CENT, rounding=ROUND_DOWN),
                deficit=max(ZERO, -net), configured=income > 0)


def load_profile(engine):
    with Session(engine) as session:
        row = session.get(Setting, "budget_profile_v1")
        return BudgetProfile(**json.loads(row.value)) if row else BudgetProfile()


def save_profile(engine, profile, *, recurring=None):
    budget_summary(profile)
    normalized = BudgetProfile(income=str(money(profile.income)), frequency=profile.frequency,
                               fixed=str(money(profile.fixed)), variable=str(money(profile.variable)),
                               reserve=str(money(profile.reserve)))
    with transaction(engine) as session:
        row = session.get(Setting, "budget_profile_v1")
        if row is None:
            row = Setting(key="budget_profile_v1", value="")
            session.add(row)
        row.value = json.dumps(asdict(normalized))
        if recurring is not None:
            from services.recurring_service import store_recurring
            store_recurring(session, recurring)


def proportional_allocation(balances, capacity):
    """Largest remainder allocation in integer cents; never exceed shared cash."""
    amounts = [int(money(value) * 100) for value in balances]
    total = sum(amounts)
    available = min(int(money(capacity) * 100), total)
    if not total:
        return [ZERO for _ in amounts]
    shares = [available * amount // total for amount in amounts]
    order = sorted(range(len(amounts)), key=lambda i: (available * amounts[i] % total, -i), reverse=True)
    for i in order[:available - sum(shares)]:
        shares[i] += 1
    return [Decimal(value) / 100 for value in shares]


def estimate_plan(profile, objectives):
    summary = budget_summary(profile)
    selected = [(o, snapshot(o)) for o in objectives if o.included]
    balances = [s["balance"] for _, s in selected]
    allocations = proportional_allocation(balances, summary["available"])
    unknown = any(s["installment"] is None for _, s in selected)
    required = None if unknown else sum((s["installment"] for _, s in selected), ZERO)
    balance = sum(balances, ZERO)
    periods = 0 if balance == 0 else (periods_needed(balance, summary["available"]) if summary["available"] else None)
    rows = []
    for (obj, s), allocation in zip(selected, allocations):
        rows.append(dict(objective=obj, snapshot=s, allocation=allocation,
                         covered=s["installment"] is not None and allocation >= s["installment"]))
    return dict(**summary, required=required, total_balance=balance, periods=periods,
                gap=None if required is None else max(ZERO, required - summary["available"]), rows=rows)
