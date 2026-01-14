from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from valutatrade_hub.core.exceptions import CurrencyNotFoundError
from valutatrade_hub.core.utils import validate_currency_code, validate_non_empty_string


class Currency(ABC):
    name: str
    code: str

    def __init__(self, name: str, code: str) -> None:
        validate_non_empty_string(name, "name")
        validate_currency_code(code)
        self.name = name
        self.code = code

    @abstractmethod
    def get_display_info(self) -> str:
        raise NotImplementedError


class FiatCurrency(Currency):
    def __init__(self, name: str, code: str, issuing_country: str) -> None:
        super().__init__(name=name, code=code)
        validate_non_empty_string(issuing_country, "issuing_country")
        self.issuing_country = issuing_country

    def get_display_info(self) -> str:
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"


class CryptoCurrency(Currency):
    def __init__(self, name: str, code: str, algorithm: str, market_cap: float) -> None:
        super().__init__(name=name, code=code)
        validate_non_empty_string(algorithm, "algorithm")
        if not isinstance(market_cap, (int, float)) or market_cap < 0:
            raise ValueError("market_cap must be a non-negative number")
        self.algorithm = algorithm
        self.market_cap = float(market_cap)

    def get_display_info(self) -> str:
        return f"[CRYPTO] {self.code} — {self.name} (Algo: {self.algorithm}, MCAP: {self.market_cap:.2e})"


# Минимальный реестр поддерживаемых валют (можно расширять)
_REGISTRY: dict[str, Currency] = {
    "USD": FiatCurrency("US Dollar", "USD", "United States"),
    "EUR": FiatCurrency("Euro", "EUR", "Eurozone"),
    "GBP": FiatCurrency("Pound Sterling", "GBP", "United Kingdom"),
    "RUB": FiatCurrency("Russian Ruble", "RUB", "Russia"),
    "BTC": CryptoCurrency("Bitcoin", "BTC", "SHA-256", 1.12e12),
    "ETH": CryptoCurrency("Ethereum", "ETH", "Ethash", 4.50e11),
    "SOL": CryptoCurrency("Solana", "SOL", "PoH/PoS", 6.50e10),
}


def get_currency(code: str) -> Currency:
    validate_currency_code(code)
    cur = _REGISTRY.get(code)
    if not cur:
        raise CurrencyNotFoundError(code)
    return cur


def list_supported_codes() -> list[str]:
    return sorted(_REGISTRY.keys())
