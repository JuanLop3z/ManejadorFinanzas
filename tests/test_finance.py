from datetime import timedelta
from decimal import Decimal
import pytest

from config.settings import today
from database.connection import create_database
from repositories.objective_repository import list_objectives
from services.finance_service import (create_objective, delete_movement, delete_objective,
    save_movement, seed_examples, snapshot, update_objectives)


def only(engine):
    return list_objectives(engine)[0]


def update(obj, **changes):
    result = dict(id=obj.id, name=obj.name, kind=obj.kind, total=str(Decimal(obj.total_cents)/100),
                  periods=obj.periods, target_date=obj.target_date, included=obj.included)
    result.update(changes)
    return result


def test_payment_correction_deletion_and_status(engine):
    oid = create_objective(engine, "Prueba", "debt", "100")
    mid = save_movement(engine, oid, "25", today(), request_id="one")
    assert snapshot(only(engine))["progress"] == Decimal("0.25")
    assert snapshot(only(engine))["installment"] == 15
    save_movement(engine, oid, "100", today(), movement_id=mid)
    assert snapshot(only(engine))["status"] == "Pagada"
    delete_movement(engine, oid, mid)
    assert snapshot(only(engine))["balance"] == 100


def test_idempotence_and_overpayments(engine):
    oid = create_objective(engine, "Prueba", "goal", "100")
    mid = save_movement(engine, oid, "60", today(), request_id="same")
    assert save_movement(engine, oid, "60", today(), request_id="same") == mid
    assert len(only(engine).movements) == 1
    for amount in ["-1", "0", "41"]:
        with pytest.raises(ValueError):
            save_movement(engine, oid, amount, today())
    with pytest.raises(ValueError):
        save_movement(engine, oid, "61", today(), request_id="same")
    assert snapshot(only(engine))["paid"] == 60


def test_persistence(engine):
    oid = create_objective(engine, "Persistente", "goal", "100.30")
    save_movement(engine, oid, "0.10", today())
    path = engine.url.database
    engine.dispose()
    from pathlib import Path
    reopened = create_database(Path(path))
    assert snapshot(only(reopened))["balance"] == Decimal("100.20")
    reopened.dispose()


def test_seed_once_classification_and_full_totals(engine):
    seed_examples(engine)
    seed_examples(engine)
    records = list_objectives(engine)
    assert len(records) == 7
    assert sum(snapshot(o)["total"] for o in records) == 9200000
    assert sum(snapshot(o)["paid"] for o in records) == 400000
    assert sum(snapshot(o)["balance"] for o in records) == 8800000
    assert sum(snapshot(o)["installment"] for o in records) == 1760000
    assert sum(snapshot(o)["balance"] for o in records if o.kind == "debt") == 4500000
    for obj in records:
        delete_objective(engine, obj.id)
    seed_examples(engine)
    assert list_objectives(engine) == []


def test_atomic_edit_and_reclassification(engine):
    first = create_objective(engine, "Primero", "debt", "100")
    create_objective(engine, "Segundo", "goal", "100")
    save_movement(engine, first, "50", today())
    a, b = list_objectives(engine)
    with pytest.raises(ValueError):
        update_objectives(engine, [update(b, name="Cambiado"), update(a, total="49")])
    assert list_objectives(engine)[1].name == "Segundo"
    update_objectives(engine, [update(a, kind="goal", included=False, periods=10)])
    obj = only(engine)
    assert obj.kind == "goal" and not obj.included
    assert snapshot(obj)["paid"] == 50
    assert snapshot(obj)["installment"] == 5


def test_dates_and_deadline_recalculation(engine):
    oid = create_objective(engine, "Prueba", "debt", "100")
    with pytest.raises(ValueError):
        save_movement(engine, oid, "10", today() + timedelta(days=1))
    save_movement(engine, oid, "10", today() - timedelta(days=1))
    assert snapshot(only(engine))["paid"] == 10
    obj = only(engine)
    obj.target_date = today() - timedelta(days=1)
    assert snapshot(obj)["installment"] is None
    obj.target_date = today() + timedelta(days=45)
    assert snapshot(obj)["periods"] >= 2


def test_delete_cascades_and_foreign_movement_protection(engine):
    a = create_objective(engine, "A", "debt", "100")
    b = create_objective(engine, "B", "goal", "100")
    mid = save_movement(engine, a, "10", today())
    with pytest.raises(ValueError):
        delete_movement(engine, b, mid)
    delete_objective(engine, a)
    from sqlalchemy.orm import Session
    from database.models import Movement
    with Session(engine) as session:
        assert session.get(Movement, mid) is None


def test_concurrent_payments_cannot_overspend(engine):
    from concurrent.futures import ThreadPoolExecutor
    oid = create_objective(engine, "Concurrente", "debt", "100")

    def pay(_):
        try:
            save_movement(engine, oid, "60", today())
            return True
        except ValueError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(pay, range(2)))
    assert sorted(results) == [False, True]
    assert snapshot(only(engine))["balance"] == 40
