from datetime import date
from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Integer, String, BigInteger
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String)


class Objective(Base):
    __tablename__ = "objectives"
    __table_args__ = (
        CheckConstraint("total_cents > 0"),
        CheckConstraint("periods > 0"),
        CheckConstraint("kind IN ('debt', 'goal')"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(10))
    total_cents: Mapped[int] = mapped_column(BigInteger)
    created_on: Mapped[date] = mapped_column(Date)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    periods: Mapped[int] = mapped_column(Integer, default=5)
    included: Mapped[bool] = mapped_column(Boolean, default=True)
    movements: Mapped[list["Movement"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="Movement.date, Movement.id"
    )


class Movement(Base):
    __tablename__ = "movements"
    __table_args__ = (CheckConstraint("amount_cents > 0"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    objective_id: Mapped[int] = mapped_column(ForeignKey("objectives.id", ondelete="CASCADE"))
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    date: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String(500), default="")
    request_id: Mapped[str] = mapped_column(String(80), unique=True)


class ExpenseObservation(Base):
    __tablename__ = "expense_observations"
    __table_args__ = (CheckConstraint("amount_cents > 0"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(String(100), unique=True)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    date: Mapped[date] = mapped_column(Date)
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    merchant: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(60))
    kind: Mapped[str] = mapped_column(String(40))
    included: Mapped[bool] = mapped_column(Boolean)
    source_url: Mapped[str] = mapped_column(String(500))
