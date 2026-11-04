from calendar import monthrange
from datetime import date
from decimal import Decimal, ROUND_CEILING

from utils.currency import money


def remaining(total, paid):
    total, paid = money(total), money(paid)
    if paid > total:
        raise ValueError("Lo acumulado no puede superar el valor objetivo.")
    return total - paid


def installment(balance, periods):
    balance = money(balance)
    if isinstance(periods, bool) or not isinstance(periods, int) or periods <= 0:
        raise ValueError("Debe haber al menos una quincena.")
    return (balance / periods).quantize(Decimal("1"), rounding=ROUND_CEILING)


def periods_needed(balance, capacity):
    balance, capacity = money(balance), money(capacity)
    if capacity <= 0:
        raise ValueError("El pago disponible debe ser mayor que cero.")
    return int((balance / capacity).to_integral_value(rounding=ROUND_CEILING))


def periods_until(start: date, target: date):
    """Count paydays on the 15th and last day, including today and target."""
    if target < start:
        return 0
    year, month = start.year, start.month
    count = 0
    while (year, month) <= (target.year, target.month):
        for day in (15, monthrange(year, month)[1]):
            count += start <= date(year, month, day) <= target
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
    return count


def progress(total, paid):
    total, paid = money(total), money(paid)
    remaining(total, paid)
    return paid / total if total else Decimal("1")
