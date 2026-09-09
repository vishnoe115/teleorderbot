from __future__ import annotations

import secrets
import time

from config import settings


def rupiah(value: int | float) -> str:
    return "Rp{:,.0f}".format(value).replace(",", ".")


def new_order_id(telegram_id: int) -> str:
    millis = int(time.time() * 1000)
    suffix = secrets.token_hex(2).upper()
    return f"INV-{telegram_id}-{millis}-{suffix}"


def random_unique_payment_code() -> int:
    """
    Generate a fresh three-digit tracking code for every order.

    The value is not persistent/global. It is regenerated on each checkout.
    It is still saved on the order row so the owner can reconcile payment.
    """
    low = max(100, min(400, settings.unique_code_min))
    high = max(low, min(400, settings.unique_code_max))
    if high == low:
        return low
    return low + secrets.randbelow(high - low + 1)
