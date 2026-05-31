import requests

_BASE    = "https://management.azure.com"
_API_VER = "2022-12-01"
_TIMEOUT = 60


def list_subscriptions(arm_token: str) -> list[dict]:
    url  = f"{_BASE}/subscriptions?api-version={_API_VER}"
    hdrs = {"Authorization": f"Bearer {arm_token}"}
    items: list[dict] = []

    while url:
        resp = requests.get(url, headers=hdrs, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        for s in data.get("value", []):
            items.append({
                "id":    s["subscriptionId"],
                "name":  s.get("displayName", s["subscriptionId"]),
                "state": s.get("state", "Unknown"),
            })
        url = data.get("nextLink")

    items.sort(key=lambda s: s["name"].lower())
    return items
