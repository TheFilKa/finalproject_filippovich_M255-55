from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from valutatrade_hub.core.exceptions import InsufficientFundsError
from valutatrade_hub.core.utils import validate_amount, validate_currency_code, validate_non_empty_string


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class User:
    def __init__(
        self,
        user_id: int,
        username: str,
        hashed_password: str,
        salt: str,
        registration_date: datetime,
    ) -> None:
        self._user_id = int(user_id)
        self.username = username
        self._hashed_password = str(hashed_password)
        self._salt = str(salt)
        self._registration_date = registration_date

    # getters/setters
    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def username(self) -> str:
        return self._username

    @username.setter
    def username(self, value: str) -> None:
        validate_non_empty_string(value, "username")
        self._username = value

    @property
    def registration_date(self) -> datetime:
        return self._registration_date

    @property
    def salt(self) -> str:
        return self._salt

    @property
    def hashed_password(self) -> str:
        return self._hashed_password

    def get_user_info(self) -> dict[str, Any]:
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date.isoformat(),
        }

    def verify_password(self, password: str) -> bool:
        validate_non_empty_string(password, "password")
        return _sha256(password + self._salt) == self._hashed_password

    def change_password(self, new_password: str) -> None:
        validate_non_empty_string(new_password, "new_password")
        if len(new_password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")
        self._hashed_password = _sha256(new_password + self._salt)


class Wallet:
    def __init__(self, currency_code: str, balance: float = 0.0) -> None:
        validate_currency_code(currency_code)
        self.currency_code = currency_code
        self.balance = balance  # goes through setter

    @property
    def balance(self) -> float:
        return self._balance

    @balance.setter
    def balance(self, value: float) -> None:
        if not isinstance(value, (int, float)):
            raise TypeError("balance must be a number")
        if float(value) < 0:
            raise ValueError("balance cannot be negative")
        self._balance = float(value)

    def deposit(self, amount: float) -> None:
        validate_amount(amount)
        self.balance = self.balance + float(amount)

    def withdraw(self, amount: float) -> None:
        validate_amount(amount)
        if amount > self.balance:
            raise InsufficientFundsError(available=self.balance, required=amount, code=self.currency_code)
        self.balance = self.balance - float(amount)

    def get_balance_info(self) -> str:
        return f"{self.currency_code}: {self.balance:.4f}"


class Portfolio:
    def __init__(self, user_id: int, wallets: dict[str, Wallet] | None = None) -> None:
        self._user_id = int(user_id)
        self._wallets: dict[str, Wallet] = wallets or {}

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def wallets(self) -> dict[str, Wallet]:
        # копия, чтобы нельзя было перезаписать напрямую
        return dict(self._wallets)

    def add_currency(self, currency_code: str) -> Wallet:
        validate_currency_code(currency_code)
        if currency_code in self._wallets:
            return self._wallets[currency_code]
        w = Wallet(currency_code=currency_code, balance=0.0)
        self._wallets[currency_code] = w
        return w

    def get_wallet(self, currency_code: str) -> Wallet | None:
        validate_currency_code(currency_code)
        return self._wallets.get(currency_code)

    def get_total_value(self, base_currency: str, exchange_rates: dict[str, float]) -> float:
        """
        Конвертирует все кошельки в base_currency по exchange_rates.
        exchange_rates: {"BTC_USD": 59337.21, ...} где формат "<FROM>_<TO>".
        """
        validate_currency_code(base_currency)
        total = 0.0
        for code, wallet in self._wallets.items():
            if code == base_currency:
                total += wallet.balance
                continue
            pair = f"{code}_{base_currency}"
            rate = exchange_rates.get(pair)
            if rate is None:
                # если курса нет — считаем 0 вклад или можно выбросить исключение на уровне usecases
                continue
            total += wallet.balance * rate
        return total

    def to_json(self) -> dict[str, Any]:
        return {
            "user_id": self._user_id,
            "wallets": {code: {"balance": w.balance} for code, w in self._wallets.items()},
        }

    @staticmethod
    def from_json(data: dict[str, Any]) -> "Portfolio":
        user_id = int(data["user_id"])
        wallets_raw: dict[str, Any] = data.get("wallets", {})
        wallets: dict[str, Wallet] = {}
        for code, wdata in wallets_raw.items():
            wallets[code] = Wallet(currency_code=code, balance=float(wdata.get("balance", 0.0)))
        return Portfolio(user_id=user_id, wallets=wallets)


@dataclass(frozen=True)
class Session:
    user_id: int
    username: str
