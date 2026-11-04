"""Reviewable local expense evidence imported from Gmail, with no account credentials."""
import hashlib
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from config.settings import local_config
from database.connection import transaction
from database.models import ExpenseObservation
from utils.currency import CENT, ZERO, money


def category_for(merchant):
    merchant = merchant.upper()
    for category, words in [
        ("Suscripciones y servicios", ["SPOTIFY", "APPLE", "CHATGPT", "CLARO", "SMART FIT"]),
        ("Transporte", ["EDS ", "ESTACION", "SERVICIO", "COMBUSCOL", "PARQUE", "GASOL", "PWS*", "CCO "]),
        ("Alimentación", ["DIDI", "FOOD", "TJV ", "VALDEZ", "PICOS", "OXXO", "RESTAUR", "RAPPI"]),
        ("Mercado", ["ARA", "EXITO", "D1 ", "JUMBO", "OLIMPICA"]),
        ("Educación", ["UNIV", "IBERO", "CORPORACION"]),
        ("Salud", ["DROG", "FARMA"]),
        ("Ocio", ["CINE", "MULTIPLEX", "STEAM", "PLAYLAND"]),
    ]:
        if any(word in merchant for word in words):
            return category
    return "Compras y otros"


def parse_bank_email(email):
    snippet = email.get("snippet", "")
    match = re.search(r"\b(Compraste|Pagaste|Retiraste|Transferiste)\s+\$([\d.,]+)", snippet, re.I)
    if not match:
        return None
    operation, raw = match.groups()
    amount = money(raw.replace(".", "").replace(",", ".") if "," in raw else raw)
    if not amount:
        return None
    stamp = datetime.fromisoformat(email["email_ts"]).astimezone(timezone(timedelta(hours=-5)))
    actual = re.search(r"\bel\s+(\d{2})/(\d{2})/(\d{2,4})\b", snippet, re.I)
    occurred = date(int(actual[3]) + (2000 if len(actual[3]) == 2 else 0), int(actual[2]), int(actual[1])) if actual else stamp.date()
    if not date(2026, 1, 1) <= occurred <= date(2026, 10, 20):
        return None
    operation = operation.lower()
    tail = snippet[match.end():].strip()
    merchant_match = re.search(r"^(?:en|a)\s+(.+?)(?:\s+con tu|\s+desde tu|\s+de tu|\s+el\s+\d)", tail, re.I)
    merchant = merchant_match[1].strip() if merchant_match else "Pago QR" if "codigo QR" in tail else "Transferencia por revisar"
    own_pattern = local_config().get("own_transfer_pattern", r"a Usuario de ejemplo|@ejemplo")
    own = operation == "transferiste" and bool(re.search(own_pattern, tail, re.I))
    kind = "Movimiento propio" if own else {"compraste": "Compra", "pagaste": "Pago", "retiraste": "Retiro de efectivo", "transferiste": "Transferencia por revisar"}[operation]
    included = operation in ("compraste", "pagaste")
    time = re.search(r"(?:a las|\d{4})\s+(\d{2}:\d{2})", snippet)
    # Exact same transaction alert across two message IDs is stored only once.
    identity = f"{occurred}|{operation}|{amount}|{merchant}|{time[1] if time else tail}"
    return dict(source_id=email["id"], fingerprint=hashlib.sha256(identity.encode()).hexdigest(),
                date=occurred, amount_cents=int(amount * 100), merchant=merchant[:200],
                category=category_for(merchant) if included else kind, kind=kind, included=included,
                source_url=email.get("display_url", ""))


def import_evidence(engine, emails):
    inserted = 0
    with transaction(engine) as session:
        known_ids = set(session.scalars(select(ExpenseObservation.source_id)))
        fingerprints = set(session.scalars(select(ExpenseObservation.fingerprint)))
        for email in emails:
            record = parse_bank_email(email)
            if record and record["source_id"] not in known_ids and record["fingerprint"] not in fingerprints:
                session.add(ExpenseObservation(**record))
                known_ids.add(record["source_id"])
                fingerprints.add(record["fingerprint"])
                inserted += 1
    return inserted


def list_expenses(engine):
    with Session(engine, expire_on_commit=False) as session:
        return list(session.scalars(select(ExpenseObservation).order_by(ExpenseObservation.date.desc(), ExpenseObservation.id.desc())))


def set_expense_included(engine, expense_id, included):
    with transaction(engine) as session:
        row = session.get(ExpenseObservation, expense_id)
        if row is None:
            raise ValueError("El gasto ya no existe.")
        row.included = included


def expense_summary(expenses):
    months = {f"2026-{month:02}": ZERO for month in range(1, 11)}
    counts = dict.fromkeys(months, 0)
    for row in expenses:
        if row.included:
            key = row.date.strftime("%Y-%m")
            if key in months:
                months[key] += Decimal(row.amount_cents)/100
                counts[key] += 1
    completed = sum((months[f"2026-{m:02}"] for m in range(1, 10)), ZERO)
    return dict(months=months, counts=counts, completed_total=completed,
                monthly_average=(completed / 9).quantize(CENT),
                missing_months=[key for key in list(months)[:9] if counts[key] == 0])
