from __future__ import annotations

import logging
import time

from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.parser_service.updater import RatesUpdater


class ParserScheduler:
    def __init__(self, updater: RatesUpdater) -> None:
        self.updater = updater
        self.logger = logging.getLogger("valutatrade.parser")
        self.settings = SettingsLoader()

    def run_forever(self) -> None:
        interval = int(self.settings.get("PARSER_UPDATE_INTERVAL_SECONDS", 300))
        self.logger.info("Scheduler started. Interval=%ds", interval)
        while True:
            self.updater.run_update()
            time.sleep(interval)
