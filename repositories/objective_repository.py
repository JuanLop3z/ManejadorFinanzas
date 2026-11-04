from sqlalchemy import select
from sqlalchemy.orm import Session
from database.models import Objective


def list_objectives(engine):
    with Session(engine, expire_on_commit=False) as session:
        return list(session.scalars(select(Objective).order_by(Objective.id)))


def require_objective(session, objective_id):
    objective = session.get(Objective, objective_id)
    if objective is None:
        raise ValueError("El registro ya no existe. Actualiza la página.")
    return objective
