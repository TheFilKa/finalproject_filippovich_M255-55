from __future__ import annotations

import os
from typing import Any

try:
    import tomllib  # py311
except ImportError:  # pragma: no cover
    tomllib = None  # type: ignore


class SettingsLoader:
    """
    Singleton через __new__:
    - простой и понятный способ обеспечить один экземпляр
    - не создаёт новых экземпляров при повторных импортах
    """
    _instance: "SettingsLoader | None" = None

    def __new__(cls) -> "SettingsLoader":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._cache = {}
            cls._instance._loaded = False
        return cls._instance

    def _load_from_pyproject(self) -> dict[str, Any]:
        # предполагаем запуск из корня проекта
        path = os.path.join(os.getcwd(), "pyproject.toml")
        if not os.path.exists(path) or tomllib is None:
            return {}
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return (data.get("tool") or {}).get("valutatrade") or {}

    def reload(self) -> None:
        self._cache = self._load_from_pyproject()
        self._loaded = True

    def get(self, key: str, default: Any = None) -> Any:
        if not self._loaded:
            self.reload()
        return self._cache.get(key, default)
