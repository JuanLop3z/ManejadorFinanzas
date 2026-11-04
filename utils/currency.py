from decimal import Decimal, InvalidOperation

CENT = Decimal("0.01")
ZERO = Decimal("0.00")
MAX_MONEY = Decimal("90000000000000.00")


def money(value):
    """Accept exact amounts only. Input uses a dot for decimals, no separators."""
    try:
        if isinstance(value, (float, bool)):
            raise ValueError("Ingresa el monto como texto, sin separadores de miles.")
        amount = Decimal(value)
        if not amount.is_finite() or amount < 0 or amount > MAX_MONEY:
            raise ValueError("El monto debe estar entre 0 y 90 billones COP.")
        if amount != amount.quantize(CENT):
            raise ValueError("Usa máximo dos decimales.")
        return amount.quantize(CENT)
    except (InvalidOperation, TypeError):
        raise ValueError("Monto inválido. Ejemplo: 1100000 o 1100000.50.") from None


def cop(value):
    amount = money(value)
    result = f"{amount:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"$ {result.removesuffix(',00')} COP"
