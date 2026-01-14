import logging
import os
from logging.handlers import RotatingFileHandler

from valutatrade_hub.infra.settings import SettingsLoader


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def configure_logging() -> None:
    """
    Настройка логирования:
    - actions.log: доменные операции BUY/SELL/LOGIN/REGISTER
    - parser.log: Parser Service

    Ротация: по размеру (1MB, 3 бэкапа).
    Формат: человекочитаемый (как в ТЗ).
    """
    settings = SettingsLoader()
    log_dir = str(settings.get("LOG_DIR", "logs"))
    _ensure_dir(log_dir)

    level_name = str(settings.get("LOG_LEVEL", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)

    fmt = logging.Formatter("%(levelname)s %(asctime)s %(name)s %(message)s")

    root = logging.getLogger()
    root.setLevel(level)

    # Не дублировать обработчики при повторном вызове
    if root.handlers:
        return

    # Console handler (удобно для CLI)
    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    # Actions file handler
    actions_file = str(settings.get("ACTIONS_LOG_FILE", "logs/actions.log"))
    ah = RotatingFileHandler(actions_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    ah.setLevel(level)
    ah.setFormatter(fmt)
    logging.getLogger("valutatrade.actions").addHandler(ah)
    logging.getLogger("valutatrade.actions").setLevel(level)
    logging.getLogger("valutatrade.actions").propagate = False

    # Parser file handler
    parser_file = str(settings.get("PARSER_LOG_FILE", "logs/parser.log"))
    ph = RotatingFileHandler(parser_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    ph.setLevel(level)
    ph.setFormatter(fmt)
    logging.getLogger("valutatrade.parser").addHandler(ph)
    logging.getLogger("valutatrade.parser").setLevel(level)
    logging.getLogger("valutatrade.parser").propagate = False
