"""Money formatting for API responses."""

SYMBOLS = {"USD": "$", "EUR": "\u20ac", "CNY": "\u00a5"}


def format_money(amount_cents: int, currency: str = "USD") -> str:
    """Render an integer cent amount as a display string."""
    symbol = SYMBOLS.get(currency, currency + " ")
    sign = "-" if amount_cents < 0 else ""
    cents = abs(amount_cents)
    return f"{sign}{symbol}{cents // 100}.{cents % 100:02d}"
