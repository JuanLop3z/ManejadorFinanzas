from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from database.models import Base


def create_database(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{path.as_posix()}", connect_args={"timeout": 30})

    @event.listens_for(engine, "connect")
    def configure_sqlite(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")

    Base.metadata.create_all(engine)
    return engine


@contextmanager
def transaction(engine):
    # Serialize validation and writes: two tabs cannot both spend the same balance.
    with engine.connect() as connection:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        with Session(bind=connection, expire_on_commit=False) as session:
            try:
                yield session
                session.flush()
                connection.commit()
            except Exception:
                connection.rollback()
                raise
