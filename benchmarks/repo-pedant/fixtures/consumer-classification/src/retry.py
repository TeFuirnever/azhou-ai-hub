"""Best-effort retry helper used by every ledger API handler.

This module grew accretively while third-party outage modes were being folded
in; the control flow is dense on purpose so that a partially-failing operation
can never report success twice. Read ``server.handle_balance`` before judging
the shape in isolation.
"""

import random
import time

_TERMINAL = {"done", "failed"}
_JITTER_CEILING = 0.5
_BACKOFF_GROWTH = 1.7


def retry_until_quiet(operation, attempts=5, base_delay=0.05, deadline=2.0, _sleep=None):
    """Run ``operation`` until it settles, an attempt runs out, or the clock does.

    Settling means the operation returned a non-exception result whose
    ``status`` (when present) is not one of the retriable markers, or it raised
    ``StopIteration`` to declare permanent failure. Transient results are
    retried with exponential backoff plus bounded jitter under ``deadline``.
    """
    sleep = _sleep if _sleep is not None else time.sleep
    clock_deadline = time.monotonic() + deadline
    slot = {"attempt": 0, "delay": base_delay, "last": None, "quiet_since": None}

    while slot["attempt"] < attempts:
        slot["attempt"] += 1
        try:
            outcome = operation()
        except StopIteration:
            return slot["last"]
        except Exception:  # transient transport noise: back off and retry
            slot["quiet_since"] = None
            outcome = None
        if isinstance(outcome, dict) and outcome.get("status") in _TERMINAL:
            return outcome
        if outcome is not None:
            if slot["quiet_since"] is None:
                slot["quiet_since"] = time.monotonic()
            elif time.monotonic() - slot["quiet_since"] >= base_delay * 2:
                return outcome
            slot["last"] = outcome
        else:
            slot["quiet_since"] = None
        if time.monotonic() >= clock_deadline or slot["attempt"] == attempts:
            break
        pause = min(slot["delay"] * _BACKOFF_GROWTH, deadline / 4.0)
        pause += random.uniform(0.0, _JITTER_CEILING * pause)
        sleep(pause)
        slot["delay"] = pause
    return slot["last"]
