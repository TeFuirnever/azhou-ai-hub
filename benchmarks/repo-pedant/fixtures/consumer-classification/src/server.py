"""HTTP handlers for the ledger API."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from format import format_money
from retry import retry_until_quiet


def handle_balance(account) -> dict:
    cents = retry_until_quiet(account.fetch_cents)
    return {"display": format_money(cents, account.currency), "cents": cents}
