"""Recurring expenses and a variable baseline from the current year's evidence."""
import json
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, ROUND_CEILING

from sqlalchemy.orm import Session

from config.settings import today
from database.models import Setting
from services.budget_service import BudgetProfile, load_profile, save_profile
from services.expense_service import list_expenses
from utils.currency import CENT, ZERO, money

RECURRING_KEY = "recurring_expenses_v1"
PATTERNS = [
    ("spotify", "Spotify", ("SPOTIFY",)),
    ("apple", "Apple", ("APPLE.COM",)),
    ("claro", "Claro móvil", ("CLARO MOVIL", "CLARO MÓVIL")),
    ("gym", "Smart Fit", ("SMART FIT",)),
    ("chatgpt", "ChatGPT", ("CHATGPT",)),
]


@dataclass(frozen=True)
class RecurringExpense:
    key: str
    name: str
    amount: str
    frequency: str = "monthly"
    enabled: bool = True
    source: str = "Ingresado manualmente"


def monthly_cost(expense):
    amount = money(expense.amount)
    if not isinstance(expense.enabled, bool):
        raise ValueError("Indica si el gasto está activo.")
    if not expense.key or not expense.name.strip():
        raise ValueError("Cada gasto fijo necesita un nombre.")
    if expense.frequency not in ("monthly", "weekly"):
        raise ValueError("La frecuencia del gasto debe ser mensual o semanal.")
    if not expense.enabled:
        return ZERO
    return (amount * 52 / 12).quantize(CENT, rounding=ROUND_CEILING) if expense.frequency == "weekly" else amount


def fixed_total(expenses):
    keys = [e.key for e in expenses]
    if len(keys) != len(set(keys)):
        raise ValueError("No se puede registrar dos veces el mismo gasto fijo.")
    return sum((monthly_cost(e) for e in expenses), ZERO)


def store_recurring(session, expenses):
    fixed_total(expenses)
    row = session.get(Setting, RECURRING_KEY)
    if row is None:
        row = Setting(key=RECURRING_KEY, value="")
        session.add(row)
    row.value = json.dumps([asdict(e) for e in expenses], ensure_ascii=False)


def load_recurring(engine):
    with Session(engine) as session:
        row = session.get(Setting, RECURRING_KEY)
        return [RecurringExpense(**values) for values in json.loads(row.value)] if row else []


def recurring_key(merchant):
    merchant = merchant.upper()
    return next((key for key, _, words in PATTERNS if any(word in merchant for word in words)), None)


def expense_baseline(observations, *, as_of=None, existing=()):
    """Use Jan 1 onward only; current month is excluded from the variable mean."""
    as_of = as_of or today()
    start = date(as_of.year, 1, 1)
    month_start = as_of.replace(day=1)
    rows = [e for e in observations if e.included and start <= e.date <= as_of]
    groups = {key: [] for key, _, _ in PATTERNS}
    variable_sum = ZERO
    for row in rows:
        key = recurring_key(row.merchant)
        if key:
            groups[key].append(row)
        elif row.date < month_start:
            variable_sum += Decimal(row.amount_cents) / 100
    # User-maintained expenses (including weekly parking) survive Gmail refreshes.
    recurring = [e for e in existing if e.key not in groups]
    for key, name, _ in PATTERNS:
        if not groups[key]:
            continue
        latest = max(groups[key], key=lambda e: (e.date, e.id))
        months = len({(e.date.year, e.date.month) for e in groups[key]})
        note = f"Gmail · último cargo {latest.date:%d/%m/%Y} · " + ("1 mes observado" if months == 1 else f"{months} meses observados")
        if months == 1:
            note += " · recurrencia estimada"
        recurring.append(RecurringExpense(key=key, name=name, amount=str(Decimal(latest.amount_cents)/100), source=note))
    complete_months = as_of.month - 1
    variable = (variable_sum / complete_months).quantize(CENT, rounding=ROUND_CEILING) if complete_months else ZERO
    return dict(recurring=recurring, variable=variable, variable_sum=variable_sum,
                months=complete_months, start=start, as_of=as_of)


def apply_expense_baseline(engine, *, as_of=None, existing=None):
    profile = load_profile(engine)
    saved = load_recurring(engine)
    extra_fixed = max(ZERO, money(profile.fixed) - fixed_total(saved))
    baseline = expense_baseline(list_expenses(engine), as_of=as_of,
                                existing=saved if existing is None else existing)
    fixed = fixed_total(baseline["recurring"]) + extra_fixed
    revised = BudgetProfile(income=profile.income, frequency=profile.frequency, fixed=str(fixed),
                            variable=str(baseline["variable"]), reserve=profile.reserve)
    save_profile(engine, revised, recurring=baseline["recurring"])
    return baseline
