import json

from config import settings
from repositories.objective_repository import list_objectives
from services.expense_service import parse_bank_email
from services.finance_service import seed_examples, snapshot


def test_private_seed_and_transfer_parameters_preserve_custom_behavior(engine):
    settings.LOCAL_CONFIG_PATH.write_text(json.dumps({
        "seed_examples": [["Objetivo local", "debt", "500", "125"]],
        "own_transfer_pattern": "a Titular de prueba|@titular_prueba",
    }), encoding="utf-8")
    seed_examples(engine)
    records = list_objectives(engine)
    assert len(records) == 1
    assert records[0].name == "Objetivo local"
    assert snapshot(records[0])["balance"] == 375
    parsed = parse_bank_email({
        "id": "synthetic-transfer",
        "snippet": "Transferiste $100.00 a Titular de prueba el 15/01/26 a las 12:00.",
        "email_ts": "2026-01-15T17:00:00+00:00",
    })
    assert parsed["kind"] == "Movimiento propio"
    assert not parsed["included"]


def test_fresh_checkout_uses_fictional_examples_without_private_config(engine):
    assert not settings.LOCAL_CONFIG_PATH.exists()
    seed_examples(engine)
    records = list_objectives(engine)
    assert len(records) == 7
    assert any(record.name == "Crédito de ejemplo" for record in records)
    assert sum(snapshot(record)["total"] for record in records) == 9200000
