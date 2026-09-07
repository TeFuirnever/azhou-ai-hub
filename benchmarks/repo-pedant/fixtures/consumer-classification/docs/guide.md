# Balance display guide

`GET /balance` returns a `display` field rendered by `format_money`. Amounts
are integer cents; the currency code selects the symbol, and unknown codes
render as the code itself followed by a space (for example `CHF 1.00`).
