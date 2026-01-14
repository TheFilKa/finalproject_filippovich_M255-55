from __future__ import annotations

import functools
import logging
from typing import Any, Callable, ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")


def log_action(action: str, verbose: bool = False) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Декоратор доменных операций.
    Логирует поля:
      action, username/user_id, currency_code, amount, rate/base (если есть),
      result (OK/ERROR), error_type/error_message.

    verbose=True: логирует доп. контекст (например, balance before/after если передали в return).
    """
    logger = logging.getLogger("valutatrade.actions")

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # По договорённости usecases передают именованные kwargs
            username = kwargs.get("username")
            user_id = kwargs.get("user_id")
            currency_code = kwargs.get("currency_code")
            amount = kwargs.get("amount")
            base = kwargs.get("base_currency") or kwargs.get("base")
            rate = kwargs.get("rate")

            who = f"user='{username}'" if username else f"user_id={user_id}"
            common = f"{action} {who} currency='{currency_code}' amount={amount}"
            if rate is not None:
                common += f" rate={rate}"
            if base is not None:
                common += f" base='{base}'"

            try:
                result = func(*args, **kwargs)
                logger.info("%s result=OK%s", common, f" verbose={result}" if verbose else "")
                return result
            except Exception as e:  # noqa: BLE001 (по ТЗ логировать любые ошибки)
                logger.info(
                    "%s result=ERROR error_type=%s error_message=%r",
                    common,
                    type(e).__name__,
                    str(e),
                )
                raise

        return wrapper

    return decorator
