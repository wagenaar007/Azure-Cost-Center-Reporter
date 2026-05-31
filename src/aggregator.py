from datetime import datetime
from collections import defaultdict


def parse_resource_id(resource_id: str) -> dict[str, str]:
    if not resource_id:
        return {
            "resource_name":  "Azure-Dienste (nicht ressourcenspezifisch)",
            "resource_type":  "N/A",
            "resource_group": "N/A",
        }

    parts       = resource_id.split("/")
    lower_parts = resource_id.lower().split("/")

    result = {
        "resource_name":  parts[-1] if parts else "Unbekannt",
        "resource_type":  "Unbekannt",
        "resource_group": "Unbekannt",
    }

    try:
        if "resourcegroups" in lower_parts:
            idx = lower_parts.index("resourcegroups")
            result["resource_group"] = parts[idx + 1] if idx + 1 < len(parts) else "Unbekannt"

        if "providers" in lower_parts:
            idx      = lower_parts.index("providers")
            provider = parts[idx + 1] if idx + 1 < len(parts) else ""
            res_type = parts[idx + 2] if idx + 2 < len(parts) else ""
            result["resource_type"] = f"{provider}/{res_type}" if provider and res_type else provider
    except (IndexError, ValueError):
        pass

    return result


def _to_dt(usage_date) -> datetime:
    return datetime.strptime(str(int(usage_date)), "%Y%m%d")


def _to_date_str(usage_date) -> str:
    return _to_dt(usage_date).strftime("%Y-%m-%d")


def enrich_daily(records: list[dict]) -> list[dict]:
    enriched = []
    for r in records:
        p = parse_resource_id(r.get("ResourceId", ""))
        enriched.append({
            **r,
            "ResourceName":  p["resource_name"],
            "ResourceType":  p["resource_type"],
            "ResourceGroup": p["resource_group"],
            "DateStr":       _to_date_str(r.get("UsageDate", "20000101")),
        })
    enriched.sort(key=lambda x: (x["DateStr"], -float(x.get("Cost", 0))))
    return enriched


def _aggregate(records: list[dict], period_fn) -> list[dict]:
    acc:  dict[tuple, float]     = defaultdict(float)
    meta: dict[tuple, dict[str, str]] = {}

    for r in records:
        dt     = _to_dt(r.get("UsageDate", "20000101"))
        period = period_fn(dt)
        rid    = r.get("ResourceId", "")
        key    = (
            period,
            r.get("SubscriptionId",   ""),
            r.get("SubscriptionName", ""),
            rid,
            r.get("ServiceName", ""),
            r.get("Currency",    "EUR"),
        )
        acc[key] += float(r.get("Cost", 0))
        if key not in meta:
            meta[key] = parse_resource_id(rid)

    result = []
    for key, cost in acc.items():
        period, sub_id, sub_name, rid, service_name, currency = key
        p = meta[key]
        result.append({
            "Period":          period,
            "SubscriptionId":  sub_id,
            "SubscriptionName": sub_name,
            "ResourceName":    p["resource_name"],
            "ResourceType":    p["resource_type"],
            "ResourceGroup":   p["resource_group"],
            "ServiceName":     service_name,
            "Cost":            round(cost, 4),
            "Currency":        currency,
        })

    result.sort(key=lambda x: (x["Period"], -x["Cost"]))
    return result


def aggregate_weekly(records: list[dict]) -> list[dict]:
    def _week(dt: datetime) -> str:
        y, w, _ = dt.isocalendar()
        return f"{y}-W{w:02d}"
    return _aggregate(records, _week)


def aggregate_monthly(records: list[dict]) -> list[dict]:
    return _aggregate(records, lambda dt: dt.strftime("%Y-%m"))


def aggregate_yearly(records: list[dict]) -> list[dict]:
    return _aggregate(records, lambda dt: str(dt.year))


def aggregate_resource_totals(records: list[dict]) -> list[dict]:
    acc:  dict[tuple, float]     = defaultdict(float)
    meta: dict[tuple, dict[str, str]] = {}

    for r in records:
        rid = r.get("ResourceId", "")
        key = (
            r.get("SubscriptionId",   ""),
            r.get("SubscriptionName", ""),
            rid,
            r.get("ServiceName", ""),
            r.get("Currency",    "EUR"),
        )
        acc[key] += float(r.get("Cost", 0))
        if key not in meta:
            meta[key] = parse_resource_id(rid)

    result = []
    for key, cost in acc.items():
        sub_id, sub_name, rid, service_name, currency = key
        p = meta[key]
        result.append({
            "SubscriptionId":   sub_id,
            "SubscriptionName": sub_name,
            "ResourceId":       rid,
            "ResourceName":     p["resource_name"],
            "ResourceType":     p["resource_type"],
            "ResourceGroup":    p["resource_group"],
            "ServiceName":      service_name,
            "TotalCost":        round(cost, 4),
            "Currency":         currency,
        })

    result.sort(key=lambda x: -x["TotalCost"])
    return result


def subscription_totals(resource_totals: list[dict]) -> list[dict]:
    acc:   dict[tuple, float] = defaultdict(float)
    count: dict[tuple, int]   = defaultdict(int)

    for r in resource_totals:
        key = (r["SubscriptionId"], r["SubscriptionName"], r.get("Currency", "EUR"))
        acc[key]   += r["TotalCost"]
        count[key] += 1

    result = [
        {
            "SubscriptionId":   k[0],
            "SubscriptionName": k[1],
            "TotalCost":        round(v, 2),
            "Currency":         k[2],
            "ResourceCount":    count[k],
        }
        for k, v in acc.items()
    ]
    result.sort(key=lambda x: -x["TotalCost"])
    return result
