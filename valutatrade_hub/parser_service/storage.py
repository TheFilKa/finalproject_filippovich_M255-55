from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from valutatrade_hub.infra.database import DatabaseManager


def utc_iso_z(dt: datetime) -> str:
    dt = dt.astimezone(timezone.utc)
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


class RatesStorage:
    def __init__(self) -> None:
        self.db = DatabaseManager()

    def append_history_records(self, records: list[dict[str, Any]]) -> None:
        history = self.db.load_history()
        existing_ids = {r.get("id") for r in history}
        for rec in records:
            if rec.get("id") not in existing_ids:
                history.append(rec)
        self.db.save_history(history)

    def upsert_snapshot_pairs(self, pairs: dict[str, dict[str, Any]], last_refresh: str) -> None:
        snap = self.db.load_rates()
        snap_pairs = snap.get("pairs") or {}

        for pair, entry in pairs.items():
            # entry: {"rate":..., "updated_at":..., "source":...}
            new_time = entry.get("updated_at")
            old_time = (snap_pairs.get(pair) or {}).get("updated_at")

            if old_time is None:
                snap_pairs[pair] = entry
                continue
            # сравнение ISO строк как datetime:
            try:
                old_dt = datetime.fromisoformat(old_time.replace("Z", "+00:00"))
                new_dt = datetime.fromisoformat(new_time.replace("Z", "+00:00"))
                if new_dt > old_dt:
                    snap_pairs[pair] = entry
            except Exception:
                snap_pairs[pair] = entry

        snap["pairs"] = snap_pairs
        snap["last_refresh"] = last_refresh
        self.db.save_rates(snap)
