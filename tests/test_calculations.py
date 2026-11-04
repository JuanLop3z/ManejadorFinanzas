from datetime import date
from decimal import Decimal
import pytest

from services.calculation_service import installment, periods_needed, periods_until, progress, remaining
from utils.currency import cop, money


def test_exact_decimal_and_upward_rounding():
    assert remaining("0.30", "0.10") == Decimal("0.20")
    assert installment("100", 3) == Decimal("34")
    assert installment("9878750", 5) == Decimal("1975750")
    assert installment("0", 5) == 0
    assert periods_needed("1000000", "300000") == 4
    assert periods_needed("0", "300000") == 0
    assert progress("100", "25") == Decimal("0.25")
    assert cop("1100000") == "$ 1.100.000 COP"
    assert cop("1100000.50") == "$ 1.100.000,50 COP"


@pytest.mark.parametrize("value", ["-1", "NaN", "Infinity", "0.001", 0.1, True, "abc", "999999999999999999999999"])
def test_invalid_amounts(value):
    with pytest.raises(ValueError):
        money(value)


@pytest.mark.parametrize("periods", [0, -1, True, 2.5])
def test_invalid_periods(periods):
    with pytest.raises(ValueError):
        installment("100", periods)


def test_invalid_balance_and_capacity():
    with pytest.raises(ValueError):
        remaining("100", "101")
    with pytest.raises(ValueError):
        periods_needed("100", "0")


def test_calendar_paydays():
    assert periods_until(date(2026, 10, 20), date(2026, 12, 31)) == 5
    assert periods_until(date(2024, 2, 15), date(2024, 2, 29)) == 2
    assert periods_until(date(2026, 10, 20), date(2026, 10, 25)) == 0
    assert periods_until(date(2026, 12, 31), date(2027, 1, 15)) == 2
    assert periods_until(date(2026, 10, 20), date(2026, 10, 19)) == 0
