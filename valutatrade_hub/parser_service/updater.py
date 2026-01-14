from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.api_clients import BaseApiClient
from valutatrade_hub.parser_service.storage import RatesStorage, utc_iso_z


class RatesUpdater:
    def __init__(self, clients: list[tuple[str, BaseApiClient]], storage: RatesStorage) -> None:
        self.clients = clients
        self.storage = storage
        self.logger = logging.getLogger("valutatrade.parser")

    def run_update(self) -> dict[str, Any]:
        self.logger.info("Starting rates update...")
        all_pairs: dict[str, dict[str, Any]] = {}
        history_records: list[dict[str, Any]] = []

        now = datetime.now(tz=timezone.utc)
        ts = utc_iso_z(now)

        errors: list[str] = []
        total_rates = 0

        for name, client in self.clients:
            self.logger.info("Fetching from %s...", name)
            t0 = time.time()
            try:
                rates = client.fetch_rates()
                ms = int((time.time() - t0) * 1000)
                self.logger.info("OK (%d rates) in %dms", len(rates), ms)

                # normalize into Core snapshot and history
                for pair, rate in rates.items():
                    all_pairs[pair] = {"rate": float(rate), "updated_at": ts, "source": name}
                    from_cur, to_cur = pair.split("_", 1)
                    history_records.append(
                        {
                            "id": f"{from_cur}_{to_cur}_{ts}",
                            "from_currency": from_cur,
                            "to_currency": to_cur,
                            "rate": float(rate),
                            "timestamp": ts,
                            "source": name,
                            "meta": {"request_ms": ms, "status_code": 200},
                        }
                    )
                total_rates += len(rates)

            except ApiRequestError as e:
                msg = f"Failed to fetch from {name}: {e}"
                errors.append(msg)
                self.logger.error(msg)
            except Exception as e:  # noqa: BLE001
                msg = f"Failed to fetch from {name}: {type(e).__name__}: {e}"
                errors.append(msg)
                self.logger.error(msg)

        if history_records:
            self.logger.info("Writing %d history records...", len(history_records))
            self.storage.append_history_records(history_records)

        if all_pairs:
            self.logger.info("Writing %d rates to snapshot...", len(all_pairs))
            self.storage.upsert_snapshot_pairs(all_pairs, last_refresh=ts)

        if errors and total_rates > 0:
            return {
                "status": "partial",
                "updated": total_rates,
                "last_refresh": ts,
                "errors": errors,
            }
        if errors and total_rates == 0:
            return {"status": "failed", "updated": 0, "last_refresh": ts, "errors": errors}
        return {"status": "ok", "updated": total_rates, "last_refresh": ts, "errors": []}
