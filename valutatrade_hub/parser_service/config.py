from __future__ import annotations

import os
from dataclasses import dataclass

from valutatrade_hub.infra.settings import SettingsLoader


@dataclass
class ParserConfig:
    EXCHANGERATE_API_KEY: str | None = os.getenv("EXCHANGERATE_API_KEY")

    COINGECKO_URL: str = "https://api.coingecko.com/api/v3/simple/price"
    EXCHANGERATE_API_URL: str = "https://v6.exchangerate-api.com/v6"

    BASE_CURRENCY: str = "USD"
    FIAT_CURRENCIES: tuple[str, ...] = ("EUR", "GBP", "RUB")
    CRYPTO_CURRENCIES: tuple[str, ...] = ("BTC", "ETH", "SOL")
    CRYPTO_ID_MAP: dict[str, str] = None  # type: ignore

    REQUEST_TIMEOUT: int = 10

    RATES_FILE_PATH: str = "data/rates.json"
    HISTORY_FILE_PATH: str = "data/exchange_rates.json"

    def __post_init__(self) -> None:
        if self.CRYPTO_ID_MAP is None:
            self.CRYPTO_ID_MAP = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana"}
        # подтянем пути из SettingsLoader, если есть
        s = SettingsLoader()
        self.RATES_FILE_PATH = str(s.get("RATES_FILE", self.RATES_FILE_PATH))
        self.HISTORY_FILE_PATH = str(s.get("HISTORY_FILE", self.HISTORY_FILE_PATH))
