# Azure Cost Center Reporter

> Cost transparency for Azure Subscriptions – Excel dashboards and interactive HTML reports.

![Platform](https://img.shields.io/badge/platform-Windows-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

**Developer:** Nils Wagenaar

---

## Features

- **Multi-Subscription** – any number of Azure subscriptions in one report
- **Cost aggregation** – costs per week, month and year
- **Resource breakdown** – costs per resource and service (ServiceName)
- **Interactive HTML report** – filterable by subscription, month and service
- **Excel dashboard** – multiple sheets (weekly, monthly, yearly, resources)
- **Local SQLite cache** – already fetched months are stored, no duplicate API calls
- **No Python required** – portable `CostCenter.exe` (PyInstaller)
- **Automatic token renewal** – no 401 errors on long runs (>1 h)
- **Rate-limit protection** – adaptive retry on HTTP 429

---

## Quick Start

### Option A – EXE (recommended, no Python required)

1. Start `CostCenter.exe`
2. Enter Tenant ID, Client ID and Client Secret (see [SETUP_SERVICE_PRINCIPAL.md](SETUP_SERVICE_PRINCIPAL.md))
3. Click **"Load"** to auto-discover subscriptions, or enter IDs manually
4. Choose date range and output file
5. Click **"Create Report"** – done

### Option B – Python directly

```bash
pip install -r requirements.txt
python gui.py          # GUI
python run.py          # CLI (requires .env file – copy from run.py header)
```

---

## Build EXE yourself

Requirements: Python 3.10+, PowerShell 7+

```powershell
.\build_exe.ps1
# EXE is then located at dist\CostCenter.exe
```

---

## Azure Permissions

See [SETUP_SERVICE_PRINCIPAL.md](SETUP_SERVICE_PRINCIPAL.md) for the full step-by-step guide.

Summary:
1. Create **App Registration** in Entra ID
2. Create a **Client Secret**
3. Assign the role **"Cost Management Reader"** to the service principal on each subscription
4. Optional: **Reader** role for role assignments (Entra groups feature)

---

## Configuration

> **The GUI does not need a `.env` file.** All settings are saved automatically in `costcenter_settings.json` next to the EXE.  
> The CLI (`run.py`) reads variables from a `.env` file.

| Variable | Required | Description |
|---|---|---|
| `TENANT_ID` | ✅ | Entra ID Directory ID |
| `CLIENT_ID` | ✅ | Application ID of the App Registration |
| `CLIENT_SECRET` | ✅ | Client Secret value (not the Secret ID) |
| `SUBSCRIPTION_IDS` | ✅ | Comma-separated subscription IDs |
| `SUBSCRIPTION_NAMES` | – | Display names (optional) |
| `DATE_FROM` | – | Start date `YYYY-MM-DD` (default: `2025-01-01`) |
| `DATE_TO` | – | End date `YYYY-MM-DD` (default: today) |
| `OUTPUT_FILE` | – | Path to the Excel output file |

---

## Project Structure

```
├── gui.py                  # GUI (CustomTkinter)
├── run.py                  # CLI entry point
├── build_exe.ps1           # EXE build script (PyInstaller)
├── requirements.txt
└── src/
    ├── aggregator.py       # Weekly/monthly/yearly aggregation
    ├── auth.py             # Azure authentication
    ├── cache.py            # SQLite cache
    ├── config.py           # Configuration (.env for CLI)
    ├── cost_client.py      # Azure Cost Management API
    ├── excel_builder.py    # Excel dashboard generation
    ├── graph_client.py     # Microsoft Graph (Entra groups)
    ├── html_builder.py     # Interactive HTML report
    └── subscription_client.py  # Subscription discovery
```

---

## Technology

| Component | Package |
|---|---|
| Azure Auth | `azure-identity` |
| HTTP | `requests` |
| GUI | `customtkinter` |
| Excel | `openpyxl` |
| Configuration (CLI) | `python-dotenv` |
| EXE build | `pyinstaller` |
| Cache | Python `sqlite3` (stdlib) |

---

## License

MIT – see [LICENSE](LICENSE)

---

## About

Developed by **Nils Wagenaar** 
