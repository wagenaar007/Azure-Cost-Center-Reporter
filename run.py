import logging
import sys
import time
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
for _noisy in ("azure", "azure.core", "azure.identity", "azure.identity._internal",
                "msal", "urllib3", "requests"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def _banner(text: str):
    line = "─" * 60
    logger.info(line)
    logger.info(f"  {text}")
    logger.info(line)


def main():
    start_time = time.perf_counter()

    _banner("Azure Cost Center Reporter")

    try:
        from src import config
    except ValueError as exc:
        logger.error(f"Konfigurationsfehler: {exc}")
        sys.exit(1)

    logger.info(f"Zeitraum     : {config.DATE_FROM}  →  {config.DATE_TO}")
    logger.info(f"Subscriptions: {len(config.SUBSCRIPTION_IDS)}")
    for sid, sname in config.SUBSCRIPTION_MAP.items():
        logger.info(f"               {sname}  ({sid})")
    logger.info(f"Output       : {config.OUTPUT_FILE}")

    _banner("Authentifizierung")
    from src.auth import get_arm_token

    try:
        arm_token = get_arm_token()
        logger.info("ARM-Token  : OK")
    except Exception as exc:
        logger.error(f"Authentifizierung fehlgeschlagen: {exc}")
        sys.exit(1)

    _banner("Lokaler Datencache")
    from src.cache import init_db, get_cache_summary

    init_db()
    cache_info = get_cache_summary()
    if cache_info:
        logger.info("Gecachte Daten:")
        for ci in cache_info:
            logger.info(
                f"  {ci['subscription_id'][:8]}…  "
                f"{ci['months_cached']} Monate ({ci['earliest']} – {ci['latest']}), "
                f"{ci['total_records']} Datensätze"
            )
    else:
        logger.info("Cache ist leer – alle Daten werden neu abgerufen.")

    _banner("Kostendaten laden (Azure Cost Management API)")
    from src.cost_client import query_daily_costs

    all_daily: list[dict] = []
    for sub_id, sub_name in zip(config.SUBSCRIPTION_IDS, config.SUBSCRIPTION_NAMES):
        try:
            records = query_daily_costs(
                token=arm_token,
                subscription_id=sub_id,
                sub_name=sub_name,
                date_from=config.DATE_FROM,
                date_to=config.DATE_TO,
            )
            all_daily.extend(records)
            logger.info(f"  {sub_name}: {len(records)} Datensätze")
        except Exception as exc:
            logger.error(f"  {sub_name}: Fehler – {exc}")
            logger.warning("  Subscription wird übersprungen.")

    if not all_daily:
        logger.error("Keine Kostendaten geladen. Berechtigungen und Subscription-IDs prüfen.")
        sys.exit(1)

    logger.info(f"Gesamt: {len(all_daily)} tägliche Datensätze geladen.")

    _banner("Daten aggregieren")
    from src import aggregator

    logger.info("Anreicherung (ResourceId parsen)...")
    daily_enriched = aggregator.enrich_daily(all_daily)

    logger.info("Wochenaggregate...")
    weekly  = aggregator.aggregate_weekly(all_daily)

    logger.info("Monatsaggregate...")
    monthly = aggregator.aggregate_monthly(all_daily)

    logger.info("Jahresaggregate...")
    yearly  = aggregator.aggregate_yearly(all_daily)

    logger.info("Ressource-Gesamtkosten...")
    resource_totals = aggregator.aggregate_resource_totals(all_daily)

    logger.info("Subscription-Summen...")
    sub_totals = aggregator.subscription_totals(resource_totals)

    logger.info(
        f"  Ressourcen gesamt : {len(resource_totals)}\n"
        f"  Wochenzeilen      : {len(weekly)}\n"
        f"  Monatszeilen      : {len(monthly)}\n"
        f"  Jahreszeilen      : {len(yearly)}"
    )

    _banner("Excel-Dashboard erstellen")
    from src.excel_builder import build_excel

    try:
        build_excel(
            output_file=config.OUTPUT_FILE,
            daily_records=daily_enriched,
            weekly_records=weekly,
            monthly_records=monthly,
            yearly_records=yearly,
            resource_totals=resource_totals,
            sub_totals=sub_totals,
            date_from=config.DATE_FROM,
            date_to=config.DATE_TO,
        )
    except Exception as exc:
        logger.error(f"Excel-Erstellung fehlgeschlagen: {exc}")
        raise

    elapsed = time.perf_counter() - start_time
    _banner(f"Fertig! ({elapsed:.1f}s)")
    logger.info(f"Report gespeichert: {config.OUTPUT_FILE}")


if __name__ == "__main__":
    main()
