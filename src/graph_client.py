import logging
import requests

logger = logging.getLogger(__name__)

_GRAPH_BASE = "https://graph.microsoft.com/v1.0"
_ARM_BASE   = "https://management.azure.com"
_TIMEOUT    = 60


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization":   f"Bearer {token}",
        "ConsistencyLevel": "eventual",
    }


def _get_all_pages(url: str, token: str) -> list[dict]:
    items: list[dict] = []
    while url:
        resp = requests.get(url, headers=_headers(token), timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        items.extend(data.get("value", []))
        url = data.get("@odata.nextLink")
    return items


def _group_type(group: dict) -> str:
    types = group.get("groupTypes", [])
    if "Unified" in types:
        return "Microsoft 365"
    if group.get("securityEnabled") and not group.get("mailEnabled"):
        return "Sicherheit"
    if group.get("mailEnabled") and not group.get("securityEnabled"):
        return "Verteilung"
    if group.get("securityEnabled") and group.get("mailEnabled"):
        return "E-Mail-aktivierte Sicherheit"
    return "Sonstige"


def _member_count(group_id: str, token: str) -> int:
    url  = f"{_GRAPH_BASE}/groups/{group_id}/members/$count"
    try:
        resp = requests.get(url, headers=_headers(token), timeout=_TIMEOUT)
        if resp.ok:
            return int(resp.text)
    except Exception as exc:
        logger.debug(f"Mitgliederzahl für {group_id} nicht abrufbar: {exc}")
    return 0


def _get_group_ids_from_role_assignments(
    arm_token: str, subscription_ids: list[str]
) -> set[str]:
    headers = {"Authorization": f"Bearer {arm_token}"}
    group_ids: set[str] = set()

    for sub_id in subscription_ids:
        url: str | None = (
            f"{_ARM_BASE}/subscriptions/{sub_id}"
            f"/providers/Microsoft.Authorization/roleAssignments"
            f"?api-version=2022-04-01"
        )
        logger.info(f"  Rollenzuweisungen lesen: {sub_id}")
        while url:
            resp = requests.get(url, headers=headers, timeout=_TIMEOUT)
            if resp.status_code == 403:
                raise PermissionError(
                    f"Kein Zugriff auf Rollenzuweisungen für Subscription {sub_id}.\n"
                    "Hinweis: Dem Service Principal die Rolle 'Reader' (zusätzlich zu "
                    "'Cost Management Reader') auf den Subscriptions zuweisen."
                )
            resp.raise_for_status()
            data = resp.json()
            for assignment in data.get("value", []):
                props = assignment.get("properties", {})
                if props.get("principalType") == "Group":
                    group_ids.add(props["principalId"])
            url = data.get("nextLink")

    return group_ids


def _fetch_group_by_id(group_id: str, graph_token: str) -> dict | None:
    url = (
        f"{_GRAPH_BASE}/groups/{group_id}"
        f"?$select=id,displayName,description,mail,groupTypes,securityEnabled,mailEnabled"
    )
    try:
        resp = requests.get(url, headers=_headers(graph_token), timeout=_TIMEOUT)
        if resp.ok:
            return resp.json()
    except Exception as exc:
        logger.debug(f"Gruppe {group_id} nicht abrufbar: {exc}")
    return None


def get_subscription_groups(
    arm_token: str, graph_token: str, subscription_ids: list[str]
) -> list[dict]:
    try:
        group_ids = _get_group_ids_from_role_assignments(arm_token, subscription_ids)
    except PermissionError as exc:
        logger.warning(str(exc))
        logger.warning("Fallback: lade ALLE Entra-Gruppen.")
        return get_all_groups(graph_token)

    if not group_ids:
        logger.info("  Keine Gruppen mit Rollenzuweisungen gefunden.")
        return []

    logger.info(f"  {len(group_ids)} Gruppen mit Rollenzuweisungen – lade Details...")
    results: list[dict] = []

    for i, gid in enumerate(sorted(group_ids), 1):
        g = _fetch_group_by_id(gid, graph_token)
        if g is None:
            continue
        count = _member_count(gid, graph_token)
        results.append({
            "GroupName":   g.get("displayName", ""),
            "Description": g.get("description") or "",
            "Mail":        g.get("mail") or "",
            "GroupType":   _group_type(g),
            "MemberCount": count,
        })
        if i % 20 == 0:
            logger.info(f"  {i}/{len(group_ids)} Gruppen verarbeitet...")

    results.sort(key=lambda x: x["GroupName"].lower())
    logger.info(f"  {len(results)} Gruppen mit Subscription-Zugriff geladen.")
    return results


def get_all_groups(token: str) -> list[dict]:
    url = (
        f"{_GRAPH_BASE}/groups"
        f"?$select=id,displayName,description,mail,groupTypes,securityEnabled,mailEnabled"
        f"&$top=999&$count=true"
    )

    logger.info("Lade alle Entra ID Gruppen (Fallback)...")
    groups = _get_all_pages(url, token)
    logger.info(f"  {len(groups)} Gruppen gefunden – lade Mitgliederzahlen...")

    results: list[dict] = []
    for i, g in enumerate(groups, 1):
        count = _member_count(g["id"], token)
        results.append({
            "GroupName":   g.get("displayName", ""),
            "Description": g.get("description") or "",
            "Mail":        g.get("mail") or "",
            "GroupType":   _group_type(g),
            "MemberCount": count,
        })
        if i % 50 == 0:
            logger.info(f"  {i}/{len(groups)} Gruppen verarbeitet...")

    results.sort(key=lambda x: x["GroupName"].lower())
    logger.info(f"  Gruppen-Abfrage abgeschlossen: {len(results)} Einträge.")
    return results
