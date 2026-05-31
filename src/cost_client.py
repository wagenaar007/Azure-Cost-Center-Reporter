import time
import logging
import email.utils
import requests
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)

_API_VERSION = "2023-11-01"
_BASE_URL    = "https://management.azure.com"
_TIMEOUT     = 120


def _headers(token_fn: Callable[[], str]) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token_fn()}",
        "Content-Type": "application/json",
    }


def _parse_retry_after_header(value: str) -> int:
    if not value:
        return 0
    try:
        return max(int(value), 1)
    except (ValueError, TypeError):
        pass
    try:
        dt = email.utils.parsedate_to_datetime(value)
        wait = int((dt - datetime.now(timezone.utc)).total_seconds())
        return max(wait, 1)
    except Exception:
        pass
    return 0


def _post(url: str, body: dict, token_fn: Callable[[], str], retry: int = 5) -> tuple[dict, bool]:
    was_throttled = False
    for attempt in range(1, retry + 1):
        resp = requests.post(url, json=body, headers=_headers(token_fn), timeout=_TIMEOUT)
        if resp.status_code == 429:
            was_throttled = True
            raw = resp.headers.get("Retry-After", "")
            logger.warning(
                f"Rate-Limit 429 – Retry-After='{raw}' (Versuch {attempt}/{retry})"
            )
            header_wait = _parse_retry_after_header(raw)
            own_backoff  = min(300, 60 * attempt)
            wait = max(header_wait, own_backoff)
            logger.warning(f"  → Warte {wait} s …")
            time.sleep(wait)
            continue
        if resp.status_code == 422:
            logger.warning(
                f"HTTP 422 – Abfrage zu groß oder ungültig: {resp.text[:200]}"
            )
            return {}, was_throttled
        resp.raise_for_status()
        return resp.json(), was_throttled
    resp.raise_for_status()
    return {}, was_throttled


def _rows_to_records(props: dict, extra: dict) -> list[dict]:
    columns = [c["name"] for c in props.get("columns", [])]
    records = []
    for row in props.get("rows", []):
        rec = dict(zip(columns, row))
        rec.update(extra)
        records.append(rec)
    return records


def _next_month(dt: datetime) -> datetime:
    if dt.month == 12:
        return datetime(dt.year + 1, 1, 1)
    return datetime(dt.year, dt.month + 1, 1)


def _query_chunk(
    token_fn: Callable[[], str],
    subscription_id: str,
    date_from: str,
    date_to: str,
) -> tuple[list[dict], bool]:
    url = (
        f"{_BASE_URL}/subscriptions/{subscription_id}"
        f"/providers/Microsoft.CostManagement/query"
        f"?api-version={_API_VERSION}"
    )
    body: dict[str, Any] = {
        "type": "ActualCost",
        "timeframe": "Custom",
        "timePeriod": {
            "from": f"{date_from}T00:00:00Z",
            "to":   f"{date_to}T23:59:59Z",
        },
        "dataSet": {
            "granularity": "Daily",
            "aggregation": {
                "totalCost": {"name": "Cost", "function": "Sum"},
            },
            "grouping": [
                {"type": "Dimension", "name": "ResourceId"},
                {"type": "Dimension", "name": "ServiceName"},
            ],
        },
    }

    records: list[dict] = []
    current_url: str | None = url
    page = 0
    was_throttled = False

    while current_url:
        page += 1
        data, throttled = _post(current_url, body, token_fn)
        if throttled:
            was_throttled = True
        props  = data.get("properties", {})
        batch  = _rows_to_records(props, {})
        records.extend(batch)
        logger.debug(f"  Seite {page}: {len(batch)} Zeilen")
        current_url = props.get("nextLink")

    return records, was_throttled


def query_daily_costs(
    token_fn: Callable[[], str],
    subscription_id: str,
    sub_name: str,
    date_from: str,
    date_to: str,
    use_cache: bool = True,
) -> list[dict]:
    from src.cache import init_db, get_cached_months, save_records, load_records

    if use_cache:
        init_db()
        cached = get_cached_months(subscription_id)
    else:
        cached = set()

    start = datetime.fromisoformat(date_from)
    end   = datetime.fromisoformat(date_to)

    chunk_start   = start.replace(day=1)
    all_records: list[dict] = []

    logger.info(f"[{sub_name}] Starte Abfrage {date_from} → {date_to}")
    if use_cache and cached:
        logger.info(f"  [{sub_name}] {len(cached)} Monat(e) bereits im Cache.")

    total_months = 0
    c = start.replace(day=1)
    while c <= end:
        if c.strftime("%Y-%m") not in cached:
            total_months += 1
        c = _next_month(c)
    if total_months > 18:
        logger.warning(
            f"  [{sub_name}] {total_months} Monate müssen frisch von der API "
            f"geladen werden – das kann lange dauern. "
            f"Tipp: Startdatum auf 2025-01-01 setzen um nur aktuelle Daten zu laden."
        )

    while chunk_start <= end:
        chunk_end_dt = min(
            _next_month(chunk_start) - timedelta(days=1),
            end,
        )
        cf = chunk_start.strftime("%Y-%m-%d")
        ct = chunk_end_dt.strftime("%Y-%m-%d")
        ym = chunk_start.strftime("%Y-%m")

        if ym in cached:
            logger.info(f"  [{sub_name}] Chunk {cf} – {ct}  ✓ aus Cache")
            all_records.extend(load_records(subscription_id, cf, ct))
        else:
            logger.info(f"  [{sub_name}] Chunk {cf} – {ct}  → Azure API")
            try:
                chunk, was_throttled = _query_chunk(token_fn, subscription_id, cf, ct)
            except requests.exceptions.HTTPError as exc:
                if getattr(exc.response, "status_code", None) == 429:
                    logger.error(
                        f"  [{sub_name}] {ym} ÜBERSPRUNGEN – anhaltende 429-Drosselung. "
                        f"Monat bleibt ungespeichert und wird beim nächsten Start neu versucht."
                    )
                    chunk_start = _next_month(chunk_start)
                    continue
                raise

            for rec in chunk:
                rec["SubscriptionId"]   = subscription_id
                rec["SubscriptionName"] = sub_name

            if use_cache:
                save_records(chunk, subscription_id, ym)

            all_records.extend(chunk)

            inter_chunk_sleep = 60
            if was_throttled:
                logger.info(f"  [{sub_name}] Nach Drosselung: warte 90 s extra …")
                inter_chunk_sleep = 90
            time.sleep(inter_chunk_sleep)

        chunk_start = _next_month(chunk_start)

    logger.info(f"[{sub_name}] {len(all_records)} Datensätze geladen.")
    return all_records
