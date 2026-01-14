from __future__ import annotations

import json
import os
import tempfile
from typing import Any

from valutatrade_hub.infra.settings import SettingsLoader


class DatabaseManager:
    """
    Singleton: единая точка доступа к JSON-хранилищу.
    """
    _instance: "DatabaseManager | None" = None

    def __new__(cls) -> "DatabaseManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._settings = SettingsLoader()
            cls._instance._ensure_data_dir()
        return cls._instance

    def _ensure_data_dir(self) -> None:
        data_dir = str(self._settings.get("DATA_DIR", "data"))
        os.makedirs(data_dir, exist_ok=True)

    def _atomic_write_json(self, path: str, data: Any) -> None:
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(prefix="tmp_", suffix=".json", dir=d or None, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, path)  # atomic on same filesystem
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def _read_json(self, path: str, default: Any) -> Any:
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return default

    # ---- users ----
    def load_users(self) -> list[dict[str, Any]]:
        path = str(self._settings.get("USERS_FILE", "data/users.json"))
        return list(self._read_json(path, default=[]))

    def save_users(self, users: list[dict[str, Any]]) -> None:
        path = str(self._settings.get("USERS_FILE", "data/users.json"))
        self._atomic_write_json(path, users)

    # ---- portfolios ----
    def load_portfolios(self) -> list[dict[str, Any]]:
        path = str(self._settings.get("PORTFOLIOS_FILE", "data/portfolios.json"))
        return list(self._read_json(path, default=[]))

    def save_portfolios(self, portfolios: list[dict[str, Any]]) -> None:
        path = str(self._settings.get("PORTFOLIOS_FILE", "data/portfolios.json"))
        self._atomic_write_json(path, portfolios)

    # ---- rates snapshot ----
    def load_rates(self) -> dict[str, Any]:
        path = str(self._settings.get("RATES_FILE", "data/rates.json"))
        return dict(self._read_json(path, default={"pairs": {}, "last_refresh": None}))

    def save_rates(self, rates: dict[str, Any]) -> None:
        path = str(self._settings.get("RATES_FILE", "data/rates.json"))
        self._atomic_write_json(path, rates)

    # ---- history ----
    def load_history(self) -> list[dict[str, Any]]:
        path = str(self._settings.get("HISTORY_FILE", "data/exchange_rates.json"))
        return list(self._read_json(path, default=[]))

    def save_history(self, history: list[dict[str, Any]]) -> None:
        path = str(self._settings.get("HISTORY_FILE", "data/exchange_rates.json"))
        self._atomic_write_json(path, history)
