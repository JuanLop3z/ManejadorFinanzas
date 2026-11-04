from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from config.settings import local_config, today
from database.connection import transaction
from database.models import Movement, Objective, Setting
from repositories.objective_repository import require_objective
from services.calculation_service import installment, periods_until, progress, remaining
from utils.currency import money


def cents(value):
    return int(money(value) * 100)


def accumulated(objective):
    return Decimal(sum(m.amount_cents for m in objective.movements)) / 100


def snapshot(objective, as_of=None):
    total = Decimal(objective.total_cents) / 100
    paid = accumulated(objective)
    balance = remaining(total, paid)
    periods = periods_until(as_of or today(), objective.target_date) if objective.target_date else objective.periods
    return dict(total=total, paid=paid, balance=balance, periods=periods,
                installment=installment(balance, periods) if periods else (Decimal(0) if not balance else None),
                progress=progress(total, paid),
                status=("Pagada" if objective.kind == "debt" else "Cumplida") if not balance else
                ("En progreso" if paid else "Pendiente"))


def validate_objective(name, kind, total, periods, target_date):
    if not name.strip() or len(name.strip()) > 120:
        raise ValueError("El nombre debe tener entre 1 y 120 caracteres.")
    if kind not in ("debt", "goal"):
        raise ValueError("Tipo de objetivo inválido.")
    if money(total) <= 0:
        raise ValueError("El valor objetivo debe ser mayor que cero.")
    installment(total, periods)
    if target_date is not None and (not isinstance(target_date, date) or target_date < today()):
        raise ValueError("La fecha objetivo no puede estar en el pasado.")


def create_objective(engine, name, kind, total, periods=5, target_date=None, included=True):
    validate_objective(name, kind, total, periods, target_date)
    with transaction(engine) as session:
        obj = Objective(name=name.strip(), kind=kind, total_cents=cents(total), periods=periods,
                        target_date=target_date, included=included, created_on=today())
        session.add(obj)
        session.flush()
        return obj.id


def update_objectives(engine, updates):
    """Save an entire edited table atomically."""
    with transaction(engine) as session:
        for data in updates:
            obj = require_objective(session, data["id"])
            target = data["target_date"]
            # Existing expired deadlines remain valid records and are surfaced as overdue.
            validate_objective(data["name"], data["kind"], data["total"], data["periods"],
                               None if target == obj.target_date else target)
            remaining(data["total"], accumulated(obj))
            obj.name, obj.kind, obj.total_cents = data["name"].strip(), data["kind"], cents(data["total"])
            obj.periods, obj.target_date, obj.included = data["periods"], target, data["included"]


def delete_objective(engine, objective_id):
    with transaction(engine) as session:
        session.delete(require_objective(session, objective_id))


def save_movement(engine, objective_id, amount, movement_date, description="", request_id=None, movement_id=None):
    amount = money(amount)
    if amount <= 0:
        raise ValueError("El aporte debe ser mayor que cero.")
    if not isinstance(movement_date, date) or movement_date > today():
        raise ValueError("La fecha del movimiento no puede estar en el futuro.")
    if len(description) > 500:
        raise ValueError("La descripción admite máximo 500 caracteres.")
    with transaction(engine) as session:
        obj = require_objective(session, objective_id)
        if request_id and movement_id is None:
            existing = session.scalar(select(Movement).where(Movement.request_id == request_id))
            if existing:
                if (existing.objective_id, existing.amount_cents, existing.date, existing.description) != (
                        objective_id, cents(amount), movement_date, description):
                    raise ValueError("Esta operación ya fue registrada con otros datos.")
                return existing.id
        movement = None
        if movement_id is not None:
            movement = session.get(Movement, movement_id)
            if movement is None or movement.objective_id != obj.id:
                raise ValueError("Movimiento no encontrado.")
        previous = Decimal(movement.amount_cents) / 100 if movement else Decimal(0)
        remaining(Decimal(obj.total_cents) / 100, accumulated(obj) - previous + amount)
        if movement is None:
            movement = Movement(objective_id=obj.id, request_id=request_id or str(uuid4()))
            session.add(movement)
        movement.amount_cents, movement.date, movement.description = cents(amount), movement_date, description
        session.flush()
        return movement.id


def delete_movement(engine, objective_id, movement_id):
    with transaction(engine) as session:
        require_objective(session, objective_id)
        movement = session.get(Movement, movement_id)
        if movement is None or movement.objective_id != objective_id:
            raise ValueError("Movimiento no encontrado.")
        session.delete(movement)


DEFAULT_EXAMPLES = [
    ("Fondo de emergencia", "goal", "1500000", "0"),
    ("Crédito de ejemplo", "debt", "2400000", "0"),
    ("Electrodoméstico", "debt", "1200000", "0"),
    ("Proyecto personal", "debt", "1000000", "400000"),
    ("Viaje de ejemplo", "goal", "800000", "0"),
    ("Curso", "debt", "300000", "0"),
    ("Equipo de trabajo", "goal", "2000000", "0"),
]


def seed_examples(engine):
    with transaction(engine) as session:
        if session.get(Setting, "examples_loaded"):
            return
        for name, kind, total, paid in local_config().get("seed_examples", DEFAULT_EXAMPLES):
            obj = Objective(name=name, kind=kind, total_cents=cents(total), created_on=today(), periods=5, included=True)
            session.add(obj)
            session.flush()
            if money(paid):
                session.add(Movement(objective_id=obj.id, amount_cents=cents(paid), date=today(),
                                     description="Saldo abonado inicial del ejemplo", request_id=f"seed-example-{obj.id}"))
        session.add(Setting(key="examples_loaded", value="1"))
