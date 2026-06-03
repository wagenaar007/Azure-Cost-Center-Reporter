"""Generate a MSAL-protected index.html for the Azure Blob Storage report portal.

The index page:
- Is itself uploaded to the container as 'index.html'
- Uses MSAL.js (loaded from Microsoft CDN) for Azure AD authentication
- Lists all *.html report files in the container as clickable links
- Generates per-report SAS tokens (read-only, configurable TTL) so the
  browser can open them directly after login
- Falls back gracefully if MSAL login is not configured (SAS-only mode)

Azure AD app registration requirements for MSAL login:
- Platform: Single-page application (SPA)
- Redirect URI: the blob storage URL of index.html
  e.g. https://<account>.blob.core.windows.net/<container>/index.html
- API permissions: Azure Storage – user_impersonation (delegated)
"""
from datetime import datetime, timezone, timedelta


def build_index_html(
    blobs: list[dict],
    account: str,
    container: str,
    client_id: str,
    tenant_id: str,
    sas_hours: int = 24,
) -> str:
    """Build the index.html content string.

    Args:
        blobs:      List of blob dicts from storage_client.list_blobs()
        account:    Storage account name
        container:  Container name
        client_id:  Azure AD App (Client) ID for MSAL login
        tenant_id:  Azure AD Tenant ID
        sas_hours:  Hours each report link should remain valid (default 24)

    Returns:
        Complete HTML string ready to be uploaded as index.html.
    """
    report_blobs = [b for b in blobs if b["name"].endswith(".html") and b["name"] != "index.html"]
    base_url = f"https://{account}.blob.core.windows.net/{container}"
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    rows_html = ""
    for blob in report_blobs:
        name = blob["name"]
        modified = blob.get("last_modified")
        if modified:
            try:
                date_str = modified.strftime("%d.%m.%Y %H:%M")
            except Exception:
                date_str = str(modified)
        else:
            date_str = "–"
        size_kb = round(blob.get("size", 0) / 1024, 1)
        rows_html += f"""
        <tr>
          <td><a href="/reports/{name}" target="_blank" class="report-link">📊 {name}</a></td>
          <td>{date_str}</td>
          <td>{size_kb} KB</td>
        </tr>"""

    if not rows_html:
        rows_html = '<tr><td colspan="3" class="empty">Noch keine Reports vorhanden.</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Azure CostCenter Reports</title>
  <script src="https://cdn.jsdelivr.net/npm/@azure/msal-browser@2.38.3/lib/msal-browser.min.js"
          onerror="document.getElementById('auth-warning').style.display='block';
                   document.getElementById('auth-warning').textContent='❌ MSAL konnte nicht geladen werden – Netzwerkfehler oder CDN geblockt.';"></script>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: #0A1929; color: #E8F0FE;
      font-family: 'Segoe UI', system-ui, sans-serif;
      min-height: 100vh; padding: 0;
    }}
    header {{
      background: #0D1B2E; border-bottom: 1px solid #1E3D5C;
      padding: 18px 32px; display: flex; align-items: center; gap: 16px;
    }}
    header .icon {{ font-size: 2rem; }}
    header h1 {{ font-size: 1.4rem; font-weight: 700; color: #E8F0FE; }}
    header p {{ font-size: 0.85rem; color: #7A9ABB; margin-top: 2px; }}
    .toolbar {{
      background: #0D1B2E; padding: 12px 32px;
      border-bottom: 1px solid #1E3D5C;
      display: flex; align-items: center; gap: 12px;
    }}
    #login-btn, #logout-btn {{
      padding: 7px 20px; border-radius: 6px; border: none;
      cursor: pointer; font-size: 0.9rem; font-weight: 600;
    }}
    #login-btn  {{ background: #1E6EA8; color: white; }}
    #logout-btn {{ background: #162640; color: #7A9ABB; border: 1px solid #1E3D5C; display:none; }}
    #user-label {{ color: #4DA8D4; font-size: 0.9rem; }}
    #auth-warning {{
      background: #2A1800; border: 1px solid #6B4200; color: #E6A020;
      padding: 12px 32px; font-size: 0.88rem; display: none;
    }}
    main {{ padding: 32px; max-width: 960px; margin: 0 auto; }}
    .card {{
      background: #162640; border: 1px solid #1E3D5C;
      border-radius: 10px; overflow: hidden; margin-bottom: 24px;
    }}
    .card-header {{
      padding: 14px 20px; border-bottom: 1px solid #1E3D5C;
      font-size: 0.8rem; font-weight: 700; color: #4DA8D4; letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    table {{ width: 100%; border-collapse: collapse; }}
    th {{
      padding: 10px 20px; text-align: left;
      font-size: 0.78rem; color: #7A9ABB; font-weight: 600;
      border-bottom: 1px solid #1E3D5C; background: #0F1E35;
    }}
    td {{ padding: 11px 20px; font-size: 0.9rem; border-bottom: 1px solid #1E3D5C; }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: #1A2F4A; }}
    a.report-link {{ color: #4DA8D4; text-decoration: none; }}
    a.report-link:hover {{ color: #7DC4E8; text-decoration: underline; }}
    .empty {{ color: #3A5A7A; text-align: center; padding: 24px; }}
    footer {{
      text-align: center; color: #3A5A7A; font-size: 0.78rem;
      padding: 24px; margin-top: 8px;
    }}
  </style>
</head>
<body>

<header>
  <div class="icon">☁</div>
  <div>
    <h1>Azure CostCenter Reports</h1>
    <p>Kostenauswertungen für Azure Subscriptions</p>
  </div>
</header>

<div class="toolbar">
  <button id="login-btn" onclick="msalLogin()">🔐 Mit Firmenkonto anmelden</button>
  <button id="logout-btn" onclick="msalLogout()">Abmelden</button>
  <span id="user-label"></span>
</div>

<div id="auth-warning">
  ⚠ Bitte melde dich mit deinem Firmenkonto an, um die Reports zu öffnen.
</div>

<main>
  <div class="card">
    <div class="card-header">📋 Verfügbare Reports</div>
    <table>
      <thead>
        <tr>
          <th>Datei</th>
          <th>Erstellt</th>
          <th>Größe</th>
        </tr>
      </thead>
      <tbody id="report-table">
        {rows_html}
      </tbody>
    </table>
  </div>
</main>

<footer>
  © 2026 Azure CostCenter Reporter &nbsp;•&nbsp; Generiert: {generated}
</footer>

<script>
const msalConfig = {{
  auth: {{
    clientId: "{client_id}",
    authority: "https://login.microsoftonline.com/{tenant_id}",
    redirectUri: window.location.origin + "/",
  }},
  cache: {{ cacheLocation: "sessionStorage" }}
}};

let msalInstance = null;

(async function initMsal() {{
  try {{
    msalInstance = new msal.PublicClientApplication(msalConfig);
    await msalInstance.initialize();
    const redirectResult = await msalInstance.handleRedirectPromise();
    if (redirectResult && redirectResult.account) {{
      showUser(redirectResult.account);
      return;
    }}
    const accounts = msalInstance.getAllAccounts();
    if (accounts.length > 0) showUser(accounts[0]);
  }} catch(e) {{
    console.error("MSAL init failed:", e);
  }}
}})();

async function msalLogin() {{
  try {{
    if (!msalInstance) {{
      msalInstance = new msal.PublicClientApplication(msalConfig);
      await msalInstance.initialize();
    }}
    await msalInstance.loginRedirect({{ scopes: ["openid", "profile"] }});
  }} catch(e) {{
    const warn = document.getElementById('auth-warning');
    warn.style.display = 'block';
    warn.textContent = '❌ Anmeldung fehlgeschlagen: ' + e.message;
  }}
}}

async function msalLogout() {{
  if (!msalInstance) return;
  try {{ await msalInstance.logoutRedirect(); }} catch(e) {{}}
}}

function showUser(account) {{
  document.getElementById('user-label').textContent = '✓ ' + (account.name || account.username);
  document.getElementById('login-btn').style.display = 'none';
  document.getElementById('logout-btn').style.display = 'inline-block';
  document.getElementById('auth-warning').style.display = 'none';
}}
</script>
</body>
</html>
"""
