from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def parse_iso_dt(value: str) -> datetime:
    # ожидаем ISO строку (с Z или без). Безопасно обрабатываем.
    v = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def validate_non_empty_string(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")


def validate_currency_code(code: Any) -> None:
    if not isinstance(code, str):
        raise ValueError("currency_code must be a string")
    c = code.strip()
    if not c:
        raise ValueError("currency_code must be non-empty")
    if c != c.upper():
        raise ValueError("currency_code must be upper-case")
    if " " in c:
        raise ValueError("currency_code must not contain spaces")
    if not (2 <= len(c) <= 5):
        raise ValueError("currency_code length must be 2..5")


def validate_amount(amount: Any) -> None:
    if not isinstance(amount, (int, float)):
        raise ValueError("'amount' должен быть положительным числом")
    if float(amount) <= 0:
        raise ValueError("'amount' должен быть положительным числом")


def is_rate_fresh(updated_at_iso: str, ttl_seconds: int) -> bool:
    updated_at = parse_iso_dt(updated_at_iso)
    age = (now_utc() - updated_at).total_seconds()
    return age <= ttl_seconds


def pair_key(from_code: str, to_code: str) -> str:
    return f"{from_code}_{to_code}"


def invert_rate(rate: float) -> float:
    if rate == 0:
        return 0.0
    return 1.0 / rate
