from datetime import date
from decimal import Decimal
from services.expense_service import expense_summary, import_evidence, list_expenses, parse_bank_email, set_expense_included


def email(id="one", text=None, timestamp="2026-01-15T17:00:00+00:00"):
    return dict(id=id, snippet=text or "Bancolombia: Compraste $123.456,78 en SPOTIFY con tu T.Deb *1234, el 15/01/2026 a las 12:00.",
                email_ts=timestamp, display_url="https://mail.google.com/mail/u/0/#all/one")


def test_bank_amount_and_date():
    parsed = parse_bank_email(email())
    assert parsed["amount_cents"] == 12345678
    assert parsed["date"] == date(2026, 1, 15)
    assert parsed["merchant"] == "SPOTIFY"
    assert parsed["included"]
    assert parse_bank_email(email(text="Promoción: compra ahora por $100")) is None
    assert parse_bank_email(email(text="Bancolombia: Compraste $100.00 en A con tu tarjeta, el 31/12/2025 a las 12:00.")) is None


def test_non_expenses_are_excluded():
    own = parse_bank_email(email(text="Bancolombia: Transferiste $250000.00 a la llave @ejemplo desde tu cuenta a Usuario de ejemplo el 15/01/26 a las 12:00."))
    assert own["kind"] == "Movimiento propio" and not own["included"]
    cash = parse_bank_email(email(text="Bancolombia: Retiraste $100.000,00 en CAJERO de tu T.Deb el 15/01/2026 a las 12:00."))
    assert not cash["included"]


def test_idempotence_review_and_complete_month_average(engine):
    data = [email(), email(id="duplicate"), email(id="october", text="Bancolombia: Pagaste $500.00 a Claro desde tu cuenta el 15/10/2026 12:00.")]
    assert import_evidence(engine, data) == 2
    assert import_evidence(engine, data) == 0
    expenses = list_expenses(engine)
    summary = expense_summary(expenses)
    assert summary["completed_total"] == Decimal("123456.78")
    assert summary["months"]["2026-10"] == 500
    assert summary["monthly_average"] == Decimal("13717.42")
    jan = next(e for e in expenses if e.date.month == 1)
    set_expense_included(engine, jan.id, False)
    assert expense_summary(list_expenses(engine))["completed_total"] == 0
    import_evidence(engine, data)
    assert not next(e for e in list_expenses(engine) if e.id == jan.id).included
