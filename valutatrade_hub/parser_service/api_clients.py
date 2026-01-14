from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import requests

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.config import ParserConfig


class BaseApiClient(ABC):
    @abstractmethod
    def fetch_rates(self) -> dict[str, float]:
        raise NotImplementedError


class CoinGeckoClient(BaseApiClient):
    def __init__(self, config: ParserConfig) -> None:
        self.config = config

    def fetch_rates(self) -> dict[str, float]:
        ids = [
            self.config.CRYPTO_ID_MAP[c]
            for c in self.config.CRYPTO_CURRENCIES
            if c in self.config.CRYPTO_ID_MAP
        ]
        if not ids:
            return {}

        params = {"ids": ",".join(ids), "vs_currencies": self.config.BASE_CURRENCY.lower()}
        try:
            r = requests.get(
                self.config.COINGECKO_URL,
                params=params,
                timeout=self.config.REQUEST_TIMEOUT,
            )
            if r.status_code != 200:
                raise ApiRequestError(f"CoinGecko status_code={r.status_code}")
            data: dict[str, Any] = r.json()
        except requests.exceptions.RequestException as e:
            raise ApiRequestError(f"CoinGecko network error: {e}") from e
        except ValueError as e:
            raise ApiRequestError(f"CoinGecko invalid JSON: {e}") from e

        out: dict[str, float] = {}
        base_key = self.config.BASE_CURRENCY.lower()
        for code, cid in self.config.CRYPTO_ID_MAP.items():
            if cid in data and base_key in data[cid]:
                out[f"{code}_{self.config.BASE_CURRENCY}"] = float(data[cid][base_key])
        return out


class ExchangeRateApiClient(BaseApiClient):
    def __init__(self, config: ParserConfig) -> None:
        self.config = config

    def fetch_rates(self) -> dict[str, float]:
        if not self.config.EXCHANGERATE_API_KEY:
            raise ApiRequestError("ExchangeRate-API key is missing (EXCHANGERATE_API_KEY)")

        url = (
            f"{self.config.EXCHANGERATE_API_URL}/"
            f"{self.config.EXCHANGERATE_API_KEY}/latest/{self.config.BASE_CURRENCY}"
        )
        try:
            r = requests.get(url, timeout=self.config.REQUEST_TIMEOUT)
            if r.status_code != 200:
                raise ApiRequestError(f"ExchangeRate-API status_code={r.status_code}")
            data: dict[str, Any] = r.json()
        except requests.exceptions.RequestException as e:
            raise ApiRequestError(f"ExchangeRate-API network error: {e}") from e
        except ValueError as e:
            raise ApiRequestError(f"ExchangeRate-API invalid JSON: {e}") from e

        if data.get("result") != "success":
            raise ApiRequestError(f"ExchangeRate-API result={data.get('result')}")

        # Оставляем fallback на rates для совместимости.
        rates: dict[str, Any] = data.get("conversion_rates") or data.get("rates") or {}
        if not rates:
            raise ApiRequestError("ExchangeRate-API returned empty rates list")

        out: dict[str, float] = {}
        # Нам нужны пары <FIAT>_USD. В ответе base=USD и conversion_rates[EUR]=0.8583 означает 1 USD = 0.8583 EUR.
        # Но по ТЗ в rates.json формат: EUR_USD = 1 EUR = X USD.
        # Поэтому инвертируем: EUR_USD = 1 / conversion_rates[EUR]
        for code in self.config.FIAT_CURRENCIES:
            if code in rates and float(rates[code]) != 0:
                out[f"{code}_{self.config.BASE_CURRENCY}"] = 1.0 / float(rates[code])

        return out
