
import logging
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

if getattr(sys, "frozen", False):
    _app_dir = Path.home() / "AppData" / "Local" / "CostCenter"
    _app_dir.mkdir(parents=True, exist_ok=True)
    _DB_PATH = _app_dir / "costcenter_cache.db"
else:
    _DB_PATH = Path(__file__).parent.parent / "costcenter_cache.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS daily_records (
                subscription_id   TEXT    NOT NULL,
                subscription_name TEXT,
                usage_date        INTEGER NOT NULL,
                resource_id       TEXT    NOT NULL DEFAULT '',
                service_name      TEXT    NOT NULL DEFAULT '',
                cost              REAL,
                currency          TEXT,
                PRIMARY KEY (subscription_id, usage_date, resource_id, service_name)
            );

            CREATE INDEX IF NOT EXISTS idx_dr_sub_date
                ON daily_records (subscription_id, usage_date);

            CREATE TABLE IF NOT EXISTS fetched_months (
                subscription_id TEXT NOT NULL,
                year_month      TEXT NOT NULL,  -- Format: YYYY-MM
                fetched_at      TEXT,
                record_count    INTEGER DEFAULT 0,
                PRIMARY KEY (subscription_id, year_month)
            );
        """)
    logger.debug("Cache initialisiert: %s", _DB_PATH)


_REFRESH_HOURS = 4  # Azure refreshes cost data every 4 hours (per Microsoft docs)


def get_cached_months(subscription_id: str) -> set:
    """Return the set of year-months that are safe to read from local cache.

    Rules:
    - current_ym  (e.g. 2026-06): always excluded – billing is live and changes
      every few hours.
    - prev_ym     (e.g. 2026-05): excluded only when the cached copy is older
      than _REFRESH_HOURS.  Re-fetching every run wastes QPU quota; Azure only
      updates data every 4 h anyway.
    """
    from datetime import date, datetime, timedelta

    now = datetime.now()
    today = date.today()
    current_ym = today.strftime("%Y-%m")
    prev_ym = (
        f"{today.year - 1}-12"
        if today.month == 1
        else f"{today.year}-{today.month - 1:02d}"
    )

    with _connect() as conn:
        rows = conn.execute(
            "SELECT year_month, fetched_at FROM fetched_months WHERE subscription_id = ?",
            (subscription_id,),
        ).fetchall()

    cached: set[str] = set()
    for r in rows:
        ym = r["year_month"]
        if ym == current_ym:
            continue  # never cache the current month
        if ym == prev_ym:
            # Only use cached copy if it is fresh enough
            fetched_at_raw = r["fetched_at"] or ""
            try:
                fetched_at = datetime.fromisoformat(fetched_at_raw)
                age_h = (now - fetched_at).total_seconds() / 3600
                if age_h <= _REFRESH_HOURS:
                    cached.add(ym)
                # else: stale → exclude so it gets re-fetched
            except (ValueError, TypeError):
                pass  # unparseable timestamp → re-fetch to be safe
            continue
        cached.add(ym)

    return cached


def load_records(subscription_id: str, date_from: str, date_to: str) -> list:
    d_from = int(date_from.replace("-", ""))
    d_to   = int(date_to.replace("-", ""))
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT subscription_id, subscription_name, usage_date,
                   resource_id, service_name, cost, currency
            FROM   daily_records
            WHERE  subscription_id = ?
              AND  usage_date BETWEEN ? AND ?
            ORDER  BY usage_date
            """,
            (subscription_id, d_from, d_to),
        ).fetchall()
    return [
        {
            "SubscriptionId":   r["subscription_id"],
            "SubscriptionName": r["subscription_name"],
            "UsageDate":        r["usage_date"],
            "ResourceId":       r["resource_id"],
            "ServiceName":      r["service_name"],
            "Cost":             r["cost"],
            "Currency":         r["currency"],
        }
        for r in rows
    ]


def save_records(records: list, subscription_id: str, year_month: str):
    rows = [
        (
            r.get("SubscriptionId", subscription_id),
            r.get("SubscriptionName", ""),
            int(r["UsageDate"]),
            r.get("ResourceId", "") or "",
            r.get("ServiceName", "") or "",
            float(r.get("Cost", 0.0)),
            r.get("Currency", "EUR"),
        )
        for r in records
    ]
    with _connect() as conn:
        if rows:
            conn.executemany(
                """
                INSERT OR REPLACE INTO daily_records
                    (subscription_id, subscription_name, usage_date,
                     resource_id, service_name, cost, currency)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        conn.execute(
            """
            INSERT OR REPLACE INTO fetched_months
                (subscription_id, year_month, fetched_at, record_count)
            VALUES (?, ?, ?, ?)
            """,
            (subscription_id, year_month, datetime.now().isoformat(), len(rows)),
        )
    logger.debug("Cache: %d Datensätze für %s/%s gespeichert.", len(rows), subscription_id, year_month)


def get_cache_summary() -> list:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT subscription_id,
                   COUNT(*)          AS months_cached,
                   MIN(year_month)   AS earliest,
                   MAX(year_month)   AS latest,
                   SUM(record_count) AS total_records
            FROM   fetched_months
            GROUP  BY subscription_id
            """
        ).fetchall()
    return [dict(r) for r in rows]


def clear_cache(subscription_id: str | None = None):
    with _connect() as conn:
        if subscription_id:
            conn.execute(
                "DELETE FROM daily_records WHERE subscription_id = ?", (subscription_id,)
            )
            conn.execute(
                "DELETE FROM fetched_months WHERE subscription_id = ?", (subscription_id,)
            )
            logger.info("Cache für %s gelöscht.", subscription_id)
        else:
            conn.execute("DELETE FROM daily_records")
            conn.execute("DELETE FROM fetched_months")
            logger.info("Gesamter Cache gelöscht.")
