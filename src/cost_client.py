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

# Azure Cost Management QPU limits (per Microsoft docs):
# 1 QPU = 1 month of data queried
# 12 QPU / 10 s  |  60 QPU / 1 min  |  600 QPU / 1 h
# 1 month per call + 60 s spacing = 1 QPU/min = proven safe under all limits
_MAX_MONTHS_PER_CHUNK = 1

# Correct rate-limit header names for Azure Cost Management Query API
_QPU_RETRY_AFTER_HEADER   = "x-ms-ratelimit-microsoft.costmanagement-qpu-retry-after"
_QPU_REMAINING_HEADER     = "x-ms-ratelimit-microsoft.costmanagement-qpu-remaining"
_QPU_CONSUMED_HEADER      = "x-ms-ratelimit-microsoft.costmanagement-qpu-consumed"


def _headers(token_fn: Callable[[], str]) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token_fn()}",
        "Content-Type": "application/json",
    }


def _parse_retry_after(resp: requests.Response) -> int:
    """Parse retry delay from Azure Cost Management response.

    Azure does NOT use the standard 'Retry-After' header for the Cost
    Management Query API.  The correct header is:
        x-ms-ratelimit-microsoft.costmanagement-qpu-retry-after
    We check it first, then fall back to the standard header.
    """
    for name in (_QPU_RETRY_AFTER_HEADER, "Retry-After"):
        value = resp.headers.get(name, "")
        if not value:
            continue
        try:
            return max(int(float(value)), 1)
        except (ValueError, TypeError):
            pass
        try:
            dt = email.utils.parsedate_to_datetime(value)
            wait = int((dt - datetime.now(timezone.utc)).total_seconds())
            return max(wait, 1)
        except Exception:
            pass
    return 0


def _log_qpu(resp: requests.Response) -> None:
    consumed  = resp.headers.get(_QPU_CONSUMED_HEADER, "")
    remaining = resp.headers.get(_QPU_REMAINING_HEADER, "")
    if consumed or remaining:
        logger.debug("  QPU verbraucht: %s | verbleibend: %s", consumed, remaining)


def _post(url: str, body: dict, token_fn: Callable[[], str], retry: int = 8) -> tuple[dict, bool]:
    was_throttled = False
    for attempt in range(1, retry + 1):
        resp = requests.post(url, json=body, headers=_headers(token_fn), timeout=_TIMEOUT)
        if resp.status_code == 429:
            was_throttled = True
            # Check every known Azure Cost Management retry header
            wait = 0
            retry_header_used = ""
            for h in [
                "x-ms-ratelimit-microsoft.costmanagement-clienttype-retry-after",
                _QPU_RETRY_AFTER_HEADER,
                "x-ms-ratelimit-microsoft.costmanagement-entity-retry-after",
                "Retry-After",
            ]:
                val = resp.headers.get(h, "")
                if val:
                    try:
                        wait = max(int(float(val)), 1)
                        retry_header_used = h.split(".")[-1] if "." in h else h
                        break
                    except (ValueError, TypeError):
                        pass
            if wait == 0:
                wait = min(300, 60 * attempt)
                logger.warning(
                    "Rate-Limit 429 (Versuch %d/%d) – kein Retry-Header, warte %d s",
                    attempt, retry, wait
                )
            else:
                logger.warning(
                    "Rate-Limit 429 (Versuch %d/%d) – %s, warte %d s",
                    attempt, retry, retry_header_used, wait
                )
            time.sleep(wait)
            continue
        if resp.status_code == 422:
            logger.warning("HTTP 422 – Abfrage zu groß oder ungültig: %s", resp.text[:200])
            return {}, was_throttled
        _log_qpu(resp)
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


def _ym_from_usage_date(usage_date: int) -> str:
    """Convert YYYYMMDD integer to YYYY-MM string."""
    s = str(usage_date)
    return f"{s[:4]}-{s[4:6]}"


def _build_fetch_ranges(
    month_list: list[str],
    cached: set[str],
) -> list[tuple[str, str, list[str]]]:
    """Build minimal API fetch ranges by grouping consecutive uncached months.

    Groups up to _MAX_MONTHS_PER_CHUNK consecutive uncached months per call,
    reducing QPU consumption (1 QPU per month of data, per Microsoft docs).

    Returns a list of (date_from, date_to, [year_months]) tuples.
    """
    uncached = [m for m in month_list if m not in cached]
    if not uncached:
        return []

    ranges: list[tuple[str, str, list[str]]] = []
    i = 0
    while i < len(uncached):
        chunk: list[str] = [uncached[i]]
        prev_dt = datetime.strptime(uncached[i], "%Y-%m")
        j = i + 1
        while j < len(uncached) and len(chunk) < _MAX_MONTHS_PER_CHUNK:
            curr_dt = datetime.strptime(uncached[j], "%Y-%m")
            if curr_dt == _next_month(prev_dt):
                chunk.append(uncached[j])
                prev_dt = curr_dt
                j += 1
            else:
                break  # gap in months → start a new range
        first_dt = datetime.strptime(chunk[0], "%Y-%m")
        last_dt  = datetime.strptime(chunk[-1], "%Y-%m")
        last_day = (_next_month(last_dt) - timedelta(days=1)).strftime("%Y-%m-%d")
        ranges.append((first_dt.strftime("%Y-%m-%d"), last_day, chunk))
        i = j
    return ranges


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
        logger.debug("  Seite %d: %d Zeilen", page, len(batch))
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

    # Build ordered list of all months in the requested range
    month_list: list[str] = []
    c = start.replace(day=1)
    while c <= end:
        month_list.append(c.strftime("%Y-%m"))
        c = _next_month(c)

    cached_count = sum(1 for m in month_list if m in cached)
    api_count    = len(month_list) - cached_count

    logger.info("[%s] Starte Abfrage %s → %s", sub_name, date_from, date_to)
    if cached_count:
        logger.info("  [%s] %d Monat(e) aus Cache, %d von API.", sub_name, cached_count, api_count)

    all_records: list[dict] = []

    # --- Load cached months ---
    for ym in month_list:
        if ym in cached:
            dt = datetime.strptime(ym, "%Y-%m")
            cf = dt.strftime("%Y-%m-%d")
            ct = (_next_month(dt) - timedelta(days=1)).strftime("%Y-%m-%d")
            all_records.extend(load_records(subscription_id, cf, ct))

    # --- Fetch uncached months in grouped chunks (up to 3 months per call) ---
    fetch_ranges = _build_fetch_ranges(month_list, cached)
    total_calls  = len(fetch_ranges)
    if fetch_ranges:
        qpu_total = sum(len(months) for _, _, months in fetch_ranges)
        logger.info(
            "  [%s] %d Monat(e) → %d API-Call(s) (%d QPU gesamt, max %d Monate/Call)",
            sub_name, api_count, total_calls, qpu_total, _MAX_MONTHS_PER_CHUNK,
        )

    for idx, (cf, ct, months_in_chunk) in enumerate(fetch_ranges, 1):
        logger.info(
            "  [%s] Call %d/%d: %s – %s  (%d Monat(e))",
            sub_name, idx, total_calls, cf, ct, len(months_in_chunk),
        )
        try:
            chunk, was_throttled = _query_chunk(token_fn, subscription_id, cf, ct)
        except requests.exceptions.HTTPError as exc:
            if getattr(exc.response, "status_code", None) == 429:
                logger.error(
                    "  [%s] %s–%s ÜBERSPRUNGEN – anhaltende 429-Drosselung. "
                    "Wird beim nächsten Start erneut versucht.",
                    sub_name, cf, ct,
                )
                continue
            raise

        for rec in chunk:
            rec["SubscriptionId"]   = subscription_id
            rec["SubscriptionName"] = sub_name

        if use_cache:
            # Split results by month so each month is cached individually
            by_month: dict[str, list] = {}
            for rec in chunk:
                ym = _ym_from_usage_date(rec.get("UsageDate", 0))
                by_month.setdefault(ym, []).append(rec)
            for ym, month_recs in by_month.items():
                save_records(month_recs, subscription_id, ym)
            # Also mark months with zero cost as cached (no empty re-fetches)
            for ym in months_in_chunk:
                if ym not in by_month:
                    save_records([], subscription_id, ym)

        all_records.extend(chunk)

        # 60 s between calls = 1 QPU/min = proven safe (never triggers any
        # QPU quota window: 12/10s, 60/min, 600/h).
        if idx < total_calls:
            time.sleep(60)

    logger.info("[%s] %d Datensätze geladen.", sub_name, len(all_records))
    return all_records
