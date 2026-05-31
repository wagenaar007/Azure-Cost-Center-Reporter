import base64
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    val = os.getenv(key, "").strip()
    if not val:
        raise ValueError(
            f"Pflichtfeld '{key}' fehlt in der .env Datei.\n"
            f"Vorlage: .env.example"
        )
    return val


def _split(value: str) -> list[str]:
    return [s.strip() for s in value.split(",") if s.strip()]


TENANT_ID     = _require("TENANT_ID")
CLIENT_ID     = _require("CLIENT_ID")
_secret_raw   = _require("CLIENT_SECRET")
if os.getenv("_secret_b64", "").strip().lower() in ("true", "1", "yes"):
    CLIENT_SECRET = base64.b64decode(_secret_raw).decode()
else:
    CLIENT_SECRET = _secret_raw

SUBSCRIPTION_IDS   = _split(_require("SUBSCRIPTION_IDS"))
_raw_names         = os.getenv("SUBSCRIPTION_NAMES", "")
SUBSCRIPTION_NAMES = _split(_raw_names)

while len(SUBSCRIPTION_NAMES) < len(SUBSCRIPTION_IDS):
    SUBSCRIPTION_NAMES.append(f"Subscription {len(SUBSCRIPTION_NAMES) + 1}")

SUBSCRIPTION_MAP: dict[str, str] = dict(zip(SUBSCRIPTION_IDS, SUBSCRIPTION_NAMES))

DATE_FROM = os.getenv("DATE_FROM", "2025-01-01").strip()
DATE_TO   = os.getenv("DATE_TO",   datetime.now().strftime("%Y-%m-%d")).strip()

OUTPUT_FILE = os.getenv("OUTPUT_FILE", "CostCenter_Report.xlsx").strip()
