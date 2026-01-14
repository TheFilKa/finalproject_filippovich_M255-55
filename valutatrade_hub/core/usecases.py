from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.decorators import log_action
from valutatrade_hub.core.exceptions import ApiRequestError, CurrencyNotFoundError, InsufficientFundsError
from valutatrade_hub.core.models import Portfolio, Session, User
from valutatrade_hub.core.utils import invert_rate, is_rate_fresh, pair_key, validate_amount, validate_currency_code
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import SettingsLoader


def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _gen_salt() -> str:
    # простая соль; можно усложнить, но по ТЗ достаточно
    return secrets.token_hex(8)


def _hash(password: str, salt: str) -> str:
    import hashlib

    return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()


class CoreService:
    def __init__(self) -> None:
        self._settings = SettingsLoader()
        self._db = DatabaseManager()
        self._session: Session | None = None

    @property
    def session(self) -> Session | None:
        return self._session

    def require_login(self) -> Session:
        if not self._session:
            raise PermissionError("Сначала выполните login")
        return self._session

    # ---------- USERS ----------
    @log_action("REGISTER")
    def register(self, username: str, password: str) -> str:
        if not isinstance(username, str) or not username.strip():
            raise ValueError("--username обязателен и не пустой")
        if not isinstance(password, str) or not password:
            raise ValueError("--password обязателен")
        if len(password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")

        users = self._db.load_users()
        if any(u["username"] == username for u in users):
            return f"Имя пользователя '{username}' уже занято"

        new_id = (max((u["user_id"] for u in users), default=0) + 1) if users else 1
        salt = _gen_salt()
        hashed = _hash(password, salt)
        reg_date = _utc_now()

        users.append(
            {
                "user_id": new_id,
                "username": username,
                "hashed_password": hashed,
                "salt": salt,
                "registration_date": reg_date.isoformat(),
            }
        )
        self._db.save_users(users)

        # создать пустой портфель
        portfolios = self._db.load_portfolios()
        portfolios.append({"user_id": new_id, "wallets": {}})
        self._db.save_portfolios(portfolios)

        return f"Пользователь '{username}' зарегистрирован (id={new_id}). Войдите: login --username {username} --password ****"

    @log_action("LOGIN")
    def login(self, username: str, password: str) -> str:
        users = self._db.load_users()
        u = next((x for x in users if x["username"] == username), None)
        if not u:
            return f"Пользователь '{username}' не найден"

        salt = u.get("salt", "")
        hashed = _hash(password, salt)
        if hashed != u.get("hashed_password"):
            return "Неверный пароль"

        self._session = Session(user_id=int(u["user_id"]), username=username)
        return f"Вы вошли как '{username}'"

    # ---------- PORTFOLIO ----------
    def _load_portfolio(self, user_id: int) -> Portfolio:
        portfolios = self._db.load_portfolios()
        raw = next((p for p in portfolios if int(p["user_id"]) == int(user_id)), None)
        if not raw:
            # если нет — создаём пустой
            return Portfolio(user_id=user_id, wallets={})
        return Portfolio.from_json(raw)

    def _save_portfolio(self, portfolio: Portfolio) -> None:
        portfolios = self._db.load_portfolios()
        found = False
        for i, p in enumerate(portfolios):
            if int(p["user_id"]) == portfolio.user_id:
                portfolios[i] = portfolio.to_json()
                found = True
                break
        if not found:
            portfolios.append(portfolio.to_json())
        self._db.save_portfolios(portfolios)

    def _get_exchange_rates_snapshot(self) -> dict[str, Any]:
        """
        rates.json формат:
        {
          "pairs": { "BTC_USD": { "rate": 59337.21, "updated_at": "...", "source": "..." }, ... },
          "last_refresh": "..."
        }
        """
        return self._db.load_rates()

    def _pairs_to_simple(self, rates_snapshot: dict[str, Any]) -> dict[str, float]:
        pairs = rates_snapshot.get("pairs") or {}
        out: dict[str, float] = {}
        for k, v in pairs.items():
            try:
                out[k] = float(v["rate"])
            except Exception:
                continue
        return out

    def show_portfolio(self, base_currency: str = "USD") -> dict[str, Any]:
        sess = self.require_login()
        validate_currency_code(base_currency)
        # валюта должна быть известна по реестру (ТЗ: ошибка неизвестной базовой)
        get_currency(base_currency)

        portfolio = self._load_portfolio(sess.user_id)
        if not portfolio.wallets:
            return {
                "empty": True,
                "message": f"Портфель пользователя '{sess.username}' пуст. Купите валюту командой buy.",
            }

        rates = self._get_exchange_rates_snapshot()
        simple_rates = self._pairs_to_simple(rates)

        rows: list[dict[str, Any]] = []
        for code, wallet in portfolio.wallets.items():
            value_in_base = wallet.balance if code == base_currency else wallet.balance * simple_rates.get(
                pair_key(code, base_currency), 0.0
            )
            rows.append(
                {
                    "currency": code,
                    "balance": wallet.balance,
                    "value_in_base": value_in_base,
                }
            )

        total = portfolio.get_total_value(base_currency=base_currency, exchange_rates=simple_rates)
        return {"empty": False, "base": base_currency, "rows": rows, "total": total, "username": sess.username}

    # ---------- BUY/SELL ----------
    @log_action("BUY", verbose=True)
    def buy(self, user_id: int, currency_code: str, amount: float, base_currency: str = "USD") -> dict[str, Any]:
        validate_amount(amount)
        validate_currency_code(currency_code)
        validate_currency_code(base_currency)

        # currency must exist (ТЗ: через currencies.get_currency)
        get_currency(currency_code)
        get_currency(base_currency)

        portfolio = self._load_portfolio(user_id)
        wallet = portfolio.get_wallet(currency_code)
        if wallet is None:
            wallet = portfolio.add_currency(currency_code)

        before = wallet.balance
        wallet.deposit(amount)
        after = wallet.balance

        # оценочная стоимость
        rate, updated_at, source = self.get_rate(from_code=currency_code, to_code=base_currency, allow_stale=True)
        est_cost = amount * rate

        self._save_portfolio(portfolio)
        return {
            "currency": currency_code,
            "amount": amount,
            "before": before,
            "after": after,
            "rate": rate,
            "base": base_currency,
            "estimated_cost": est_cost,
            "updated_at": updated_at,
            "source": source,
        }

    @log_action("SELL", verbose=True)
    def sell(self, user_id: int, currency_code: str, amount: float, base_currency: str = "USD") -> dict[str, Any]:
        validate_amount(amount)
        validate_currency_code(currency_code)
        validate_currency_code(base_currency)

        get_currency(currency_code)
        get_currency(base_currency)

        portfolio = self._load_portfolio(user_id)
        wallet = portfolio.get_wallet(currency_code)
        if wallet is None:
            raise ValueError(
                f"У вас нет кошелька '{currency_code}'. Добавьте валюту: она создаётся автоматически при первой покупке."
            )

        before = wallet.balance
        # withdraw может бросить InsufficientFundsError (ТЗ)
        wallet.withdraw(amount)
        after = wallet.balance

        rate, updated_at, source = self.get_rate(from_code=currency_code, to_code=base_currency, allow_stale=True)
        revenue = amount * rate

        self._save_portfolio(portfolio)
        return {
            "currency": currency_code,
            "amount": amount,
            "before": before,
            "after": after,
            "rate": rate,
            "base": base_currency,
            "estimated_revenue": revenue,
            "updated_at": updated_at,
            "source": source,
        }

    # ---------- GET RATE ----------
    def get_rate(
        self,
        from_code: str,
        to_code: str,
        allow_stale: bool = False,
    ) -> tuple[float, str, str]:
        """
        Возвращает (rate, updated_at, source).
        TTL берём из SettingsLoader.
        Если устарело и allow_stale=False -> ApiRequestError (Core не обязан сам ходить в сеть).
        """
        validate_currency_code(from_code)
        validate_currency_code(to_code)

        # валидируем через реестр (ТЗ: иначе CurrencyNotFoundError)
        get_currency(from_code)
        get_currency(to_code)

        ttl = int(self._settings.get("RATES_TTL_SECONDS", 300))
        rates = self._db.load_rates()
        pairs = rates.get("pairs") or {}
        key = pair_key(from_code, to_code)
        if key in pairs:
            entry = pairs[key]
            updated_at = entry.get("updated_at")
            source = entry.get("source", "unknown")
            rate = float(entry.get("rate"))
            if updated_at and is_rate_fresh(updated_at, ttl):
                return rate, updated_at, source
            if allow_stale:
                return rate, updated_at or "unknown", source
            raise ApiRequestError("Кеш устарел (TTL). Выполните update-rates или повторите позже.")

        # обратный курс из кеша, если есть
        inv_key = pair_key(to_code, from_code)
        if inv_key in pairs:
            entry = pairs[inv_key]
            updated_at = entry.get("updated_at")
            source = entry.get("source", "unknown")
            inv_rate = float(entry.get("rate"))
            rate = invert_rate(inv_rate)
            if updated_at and is_rate_fresh(updated_at, ttl):
                return rate, updated_at, source
            if allow_stale:
                return rate, updated_at or "unknown", source
            raise ApiRequestError("Кеш устарел (TTL). Выполните update-rates или повторите позже.")

        raise ApiRequestError(f"Курс {from_code}→{to_code} недоступен. Повторите попытку позже.")
