from __future__ import annotations

import html as _html
import json
from datetime import datetime
from collections import defaultdict
from pathlib import Path


def _esc(value) -> str:
    return _html.escape(str(value))


def _eur(value: float) -> str:
    formatted = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{formatted}&nbsp;€"


def _month_label(period: str) -> str:
    try:
        y, m = period.split("-")
        months = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun",
                  "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
        return f"{months[int(m) - 1]} {y[2:]}"
    except Exception:
        return period


_CSS = """\
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: Calibri, 'Segoe UI', Arial, sans-serif; background: #eef3f8; color: #1a2a3a; font-size: 14px; }
.hdr { background: linear-gradient(135deg, #1e3a5f 0%, #2e75b6 100%); color: white; padding: 22px 40px; }
.hdr h1 { font-size: 26px; font-weight: 700; letter-spacing: -0.5px; }
.hdr .meta { font-size: 12px; color: #a0c8e8; margin-top: 6px; }
.wrap { max-width: 1400px; margin: 24px auto; padding: 0 24px; }
.sec { background: white; border-radius: 10px; padding: 20px 24px; margin-bottom: 20px;
       box-shadow: 0 2px 8px rgba(0,0,0,.07); }
h2 { font-size: 15px; color: #1e3a5f; margin-bottom: 14px; font-weight: 700;
     padding-bottom: 8px; border-bottom: 2px solid #dde8f4; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
thead th { background: #1e3a5f; color: white; padding: 9px 14px; text-align: left;
           font-weight: 600; white-space: nowrap; }
thead th.r { text-align: right; }
tbody td { padding: 7px 14px; border-bottom: 1px solid #e8f0f8; white-space: nowrap; }
tbody td.r { text-align: right; font-variant-numeric: tabular-nums; }
tbody tr:nth-child(even) td { background: #f0f6fb; }
tbody tr.tot td { background: #bdd7ee !important; font-weight: 700; }
.up { color: #c0392b; font-weight: 600; }
.dn { color: #1a8c3f; font-weight: 600; }
.nd { color: #999; }
.legend { display: flex; gap: 18px; margin-bottom: 12px; font-size: 12px; color: #555; flex-wrap: wrap; }
.dot { display: inline-block; width: 12px; height: 12px; border-radius: 3px; margin-right: 4px; vertical-align: middle; }
.svc-tbl td, .svc-tbl th { font-size: 12px; padding: 6px 10px; }
.svc-name { max-width: 260px; overflow: hidden; text-overflow: ellipsis; }
.filter-note { font-weight: 400; font-size: 12px; color: #888; margin-left: 8px; }
.no-sel { color: #999; font-style: italic; padding: 12px 0; }
.yr-grp { display: flex; align-items: center; gap: 5px; margin-bottom: 8px; flex-wrap: wrap; }
.yr-lbl { font-size: 12px; font-weight: 700; color: #1e3a5f; min-width: 36px; }
.m-btn { padding: 5px 10px; border-radius: 6px; border: 1.5px solid #b0c8e4;
         background: white; color: #3a5a7a; font-size: 12px; font-family: inherit;
         cursor: pointer; transition: all .15s; }
.m-btn:hover { background: #dde8f4; border-color: #2e75b6; }
.m-btn.active { background: #1e3a5f; color: white; border-color: #1e3a5f; font-weight: 600; }
.q-btns { display: flex; gap: 8px; flex-wrap: wrap; }
.q-btn { padding: 7px 16px; border-radius: 7px; border: 1.5px solid #b0c8e4;
         background: white; color: #1e3a5f; font-size: 13px; font-family: inherit;
         cursor: pointer; transition: all .15s; font-weight: 600; }
.q-btn:hover { background: #dde8f4; border-color: #2e75b6; }
.q-btn-primary { background: #2e75b6; color: white; border-color: #2e75b6; }
.q-btn-primary:hover { background: #1a5a9e; }
.q-btn-danger { background: white; color: #c0392b; border-color: #e8b0a8; }
.q-btn-danger:hover { background: #fde8e4; }
.cards-row { display: flex; gap: 16px; margin-bottom: 20px; flex-wrap: wrap; }
.card { background: white; border-radius: 10px; padding: 18px 22px; flex: 1; min-width: 160px;
        box-shadow: 0 2px 8px rgba(0,0,0,.07); border-top: 3px solid #2e75b6; }
.card-val { font-size: 20px; font-weight: 700; color: #1e3a5f; line-height: 1.3; }
.card-lbl { font-size: 11px; color: #888; margin-top: 4px; }
.btn-print { background: rgba(255,255,255,.15); color: white;
             border: 1px solid rgba(255,255,255,.45); padding: 9px 20px;
             border-radius: 6px; font-size: 14px; font-family: inherit; cursor: pointer; }
.btn-print:hover { background: rgba(255,255,255,.28); }
@media print {
  .btn-print, .sec-filter { display: none !important; }
  body { background: white !important; font-size: 12px; }
  .hdr { background: #1e3a5f !important;
         -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important;
         padding: 14px 24px; }
  .hdr h1 { font-size: 20px; }
  .wrap { max-width: 100%; margin: 0; padding: 6px 0; }
  .sec { box-shadow: none !important; border: 1px solid #ccd8e8;
         margin-bottom: 8px; padding: 12px 16px; border-radius: 4px; }
  .sec-chart { break-before: page; break-inside: avoid; }
  h2 { color: #1e3a5f !important; }
  table { font-size: 11px; }
  thead th, tbody tr:nth-child(even) td, tbody tr.tot td {
    -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
  .up { color: #c0392b !important; }
  .dn { color: #1a8c3f !important; }
  canvas { max-width: 100% !important; }
  .cards-row { flex-wrap: wrap; }
  .card { min-width: 140px; }
  @page { size: A4; margin: 12mm; }
}
"""


_JS = """\
const DATA = __DATA_JSON__;
let sel = new Set(DATA.months);
let selSubs = new Set(DATA.subs);

function eur(v) {
  return v.toLocaleString("de-DE", {minimumFractionDigits:2, maximumFractionDigits:2}) + "\u00a0\u20ac";
}
function eurSign(v) { return (v >= 0 ? "+" : "") + eur(v); }
function ml(p) {
  const mns = ["Jan","Feb","M\u00e4r","Apr","Mai","Jun","Jul","Aug","Sep","Okt","Nov","Dez"];
  const [y, m] = p.split("-");
  return mns[+m - 1] + " " + y.slice(2);
}
function selMonths()   { return DATA.months.filter(m => sel.has(m)); }
function selSubsList() { return DATA.subs.filter(s => selSubs.has(s)); }
function subCost(sub, months) {
  const d = DATA.pivot[sub] || {};
  return months.reduce((s, m) => s + (d[m] || 0), 0);
}
function svcCost(svc, months) {
  return selSubsList().reduce((tot, sub) => {
    const d = ((DATA.svcPivot[sub] || {})[svc]) || {};
    return tot + months.reduce((s, m) => s + (d[m] || 0), 0);
  }, 0);
}
function grandCost(months) {
  return selSubsList().reduce((s, sub) => s + subCost(sub, months), 0);
}

// ── Month buttons ─────────────────────────────────────────────────────────────
function renderMonthBtns() {
  const byYear = {};
  DATA.months.forEach(m => { const y = m.slice(0,4); (byYear[y] = byYear[y] || []).push(m); });
  let html = "";
  for (const [y, ms] of Object.entries(byYear)) {
    html += `<div class="yr-grp"><span class="yr-lbl">${y}</span>`;
    ms.forEach(m => {
      html += `<button class="m-btn ${sel.has(m) ? "active" : ""}" onclick="toggle('${m}')">${ml(m)}</button>`;
    });
    html += "</div>";
  }
  document.getElementById("month-btns").innerHTML = html;
}

function toggle(m) { sel.has(m) ? sel.delete(m) : sel.add(m); renderAll(); }
function selectAll()  { sel = new Set(DATA.months); renderAll(); }
function clearSel()   { sel = new Set(); renderAll(); }
function selectLast(n){ sel = new Set(DATA.months.slice(-n)); renderAll(); }
function selectYear(y){ sel = new Set(DATA.months.filter(m => m.startsWith(y))); renderAll(); }

// ── Subscription buttons ──────────────────────────────────────────────────────
function renderSubBtns() {
  let html = "";
  DATA.subs.forEach(s => {
    const safe = s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
    html += `<button class="m-btn ${selSubs.has(s)?"active":""}" onclick="toggleSub(this)" data-sub="${safe}">${safe}</button> `;
  });
  document.getElementById("sub-btns").innerHTML = html;
}
function toggleSub(btn) {
  const s = btn.dataset.sub;
  selSubs.has(s) ? selSubs.delete(s) : selSubs.add(s);
  renderAll();
}
function selectAllSubs() { selSubs = new Set(DATA.subs); renderAll(); }
function clearSelSubs()  { selSubs = new Set(); renderAll(); }

// ── Summary cards ─────────────────────────────────────────────────────────────
function renderSummary() {
  const ms = selMonths();
  const n  = ms.length;
  const tot = grandCost(ms);
  let deltaHTML = "<span class='nd'>\u2013</span>";
  let pctHTML   = "<span class='nd'>\u2013</span>";
  if (n >= 2) {
    const first = grandCost([ms[0]]);
    const last  = grandCost([ms[n - 1]]);
    const d   = last - first;
    const pct = first > 0 ? d / first * 100 : 0;
    const cls = d > 0 ? "up" : d < 0 ? "dn" : "nd";
    deltaHTML = `<span class="${cls}">${eurSign(d)}</span>`;
    pctHTML   = `<span class="${cls}">${(pct >= 0 ? "+" : "")}${pct.toFixed(1)}\u00a0%</span>`;
  }
  document.getElementById("summary-cards").innerHTML = `
    <div class="cards-row">
      <div class="card"><div class="card-val">${n}</div>
        <div class="card-lbl">Monate ausgew&auml;hlt</div></div>
      <div class="card"><div class="card-val">${eur(tot)}</div>
        <div class="card-lbl">Summe gew&auml;hlter Monate</div></div>
      <div class="card"><div class="card-val">${deltaHTML}</div>
        <div class="card-lbl">Erster &rarr; Letzter Monat (&euro;)</div></div>
      <div class="card"><div class="card-val">${pctHTML}</div>
        <div class="card-lbl">Ver&auml;nderung in&nbsp;%</div></div>
    </div>`;
}

// ── Canvas chart ──────────────────────────────────────────────────────────────
function drawChart() {
  const ms = selMonths();
  const canvas = document.getElementById("chart");
  const DPR = window.devicePixelRatio || 1;
  const W = Math.max((canvas.parentElement || canvas).clientWidth - 4, 300);
  if (!ms.length) {
    canvas.width = W * DPR; canvas.height = 80 * DPR; canvas.style.height = "80px";
    const ctx = canvas.getContext("2d"); ctx.scale(DPR, DPR);
    ctx.fillStyle = "#f8fbff"; ctx.fillRect(0, 0, W, 80);
    ctx.fillStyle = "#aaa"; ctx.font = "14px Calibri,Arial";
    ctx.textAlign = "center"; ctx.fillText("Keine Monate ausgew\u00e4hlt", W / 2, 44);
    return;
  }
  const H = 290;
  canvas.width = W * DPR; canvas.height = H * DPR; canvas.style.height = H + "px";
  const ctx = canvas.getContext("2d"); ctx.scale(DPR, DPR);
  const totals = ms.map(m => grandCost([m]));
  const maxV = (Math.max(...totals) || 1) * 1.08;
  const PL = 78, PR = 20, PT = 24, PB = 58;
  const pw = W - PL - PR, ph = H - PT - PB, n = ms.length;
  const barW = Math.min(48, Math.max(6, Math.floor(pw / n - 5)));
  const gap  = n > 1 ? Math.max(2, (pw - n * barW) / (n - 1)) : 0;
  ctx.fillStyle = "#f8fbff"; ctx.beginPath();
  if (ctx.roundRect) ctx.roundRect(0, 0, W, H, 8); else ctx.rect(0, 0, W, H);
  ctx.fill();
  for (let i = 0; i <= 4; i++) {
    const y = PT + ph - ph * (i / 4);
    ctx.strokeStyle = "#dde8f4"; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(PL, y); ctx.lineTo(W - PR, y); ctx.stroke();
    const val = maxV * (i / 4);
    ctx.fillStyle = "#888"; ctx.font = "11px Calibri,Arial"; ctx.textAlign = "right";
    ctx.fillText((val >= 1000 ? (val / 1000).toFixed(0) + "k" : val.toFixed(0)) + " \u20ac", PL - 6, y + 4);
  }
  totals.forEach((total, i) => {
    const bh = Math.max(1, ph * total / maxV);
    const x  = PL + i * (barW + gap), y = PT + ph - bh;
    let color, stroke;
    if      (i === 0)                          { color = "#2e75b6"; stroke = "#1a4f8a"; }
    else if (total > totals[i-1] * 1.005)      { color = "#c0392b"; stroke = "#922b21"; }
    else if (total < totals[i-1] * 0.995)      { color = "#27ae60"; stroke = "#1a7a43"; }
    else                                       { color = "#2e75b6"; stroke = "#1a4f8a"; }
    ctx.globalAlpha = 0.88;
    ctx.fillStyle = color; ctx.strokeStyle = stroke; ctx.lineWidth = 0.5;
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(x, y, barW, bh, 2); else ctx.rect(x, y, barW, bh);
    ctx.fill(); ctx.stroke(); ctx.globalAlpha = 1;
    if (bh > 22 && barW >= 16) {
      ctx.fillStyle = stroke; ctx.font = "9px Calibri,Arial"; ctx.textAlign = "center";
      ctx.fillText(total >= 1000 ? (total / 1000).toFixed(1) + "k" : total.toFixed(0), x + barW / 2, y - 4);
    }
    const lx = x + barW / 2; ctx.fillStyle = "#555";
    if (n > 14) {
      ctx.font = "9px Calibri,Arial"; ctx.save();
      ctx.translate(lx, H - PB + 10); ctx.rotate(-Math.PI / 4);
      ctx.textAlign = "right"; ctx.fillText(ml(ms[i]), 0, 0); ctx.restore();
    } else {
      ctx.font = "10px Calibri,Arial"; ctx.textAlign = "center";
      ctx.fillText(ml(ms[i]), lx, H - PB + 16);
    }
  });
  ctx.strokeStyle = "#2e75b6"; ctx.lineWidth = 1.5;
  ctx.beginPath(); ctx.moveTo(PL, PT + ph); ctx.lineTo(W - PR, PT + ph); ctx.stroke();
}

// ── Subscription table ────────────────────────────────────────────────────────
function renderSubTable() {
  const ms = selMonths(), n = ms.length;
  const activeSubs = selSubsList();
  const mNote = n < DATA.months.length ? `${n} von ${DATA.months.length} Monate` : "alle Monate";
  const sNote = activeSubs.length < DATA.subs.length ? `, ${activeSubs.length} von ${DATA.subs.length} Abos` : "";
  document.getElementById("sub-filter-note").textContent = `(${mNote}${sNote})`;
  if (!ms.length || !activeSubs.length) {
    document.getElementById("sub-table").innerHTML = "<p class='no-sel'>Keine Monate/Abos ausgew\u00e4hlt.</p>";
    return;
  }
  const hasDelta = n >= 2;
  let html = "<table><thead><tr><th>Monat</th>";
  activeSubs.forEach(s => { html += `<th class="r">${s}</th>`; });
  html += '<th class="r">Gesamt</th>';
  if (hasDelta) html += '<th class="r">Gg.&nbsp;Vormonat</th>';
  html += "</tr></thead><tbody>";
  const allTots = ms.map(m => grandCost([m]));
  ms.forEach((m, i) => {
    const tot = allTots[i];
    html += `<tr><td>${ml(m)}</td>`;
    activeSubs.forEach(sub => { html += `<td class="r">${eur(subCost(sub, [m]))}</td>`; });
    html += `<td class="r"><strong>${eur(tot)}</strong></td>`;
    if (hasDelta) {
      if (i === 0) {
        html += "<td class='r nd'>\u2013</td>";
      } else {
        const d = tot - allTots[i - 1];
        const pct = allTots[i - 1] > 0 ? d / allTots[i - 1] * 100 : 0;
        const cls = d > 0 ? "up" : d < 0 ? "dn" : "nd";
        html += `<td class="r ${cls}">${eurSign(d)}<br><small>${(pct >= 0 ? "+" : "")}${pct.toFixed(1)}\u00a0%</small></td>`;
      }
    }
    html += "</tr>";
  });
  const grandTot = grandCost(ms);
  html += `<tr class="tot"><td>GESAMT</td>`;
  activeSubs.forEach(sub => { html += `<td class="r">${eur(subCost(sub, ms))}</td>`; });
  html += `<td class="r">${eur(grandTot)}</td>`;
  if (hasDelta) {
    const d = allTots[n - 1] - allTots[0];
    const pct = allTots[0] > 0 ? d / allTots[0] * 100 : 0;
    const cls = d > 0 ? "up" : d < 0 ? "dn" : "nd";
    html += `<td class="r ${cls}">${eurSign(d)}<br><small>${(pct >= 0 ? "+" : "")}${pct.toFixed(1)}\u00a0%</small></td>`;
  }
  html += "</tr></tbody></table>";
  document.getElementById("sub-table").innerHTML = html;
}

// ── Service table ─────────────────────────────────────────────────────────────
function renderSvcTable() {
  const ms = selMonths(), n = ms.length;
  const activeSubs = selSubsList();
  const mNote = n < DATA.months.length ? `${n} von ${DATA.months.length} Monate` : "alle Monate";
  const sNote = activeSubs.length < DATA.subs.length ? `, ${activeSubs.length} von ${DATA.subs.length} Abos` : "";
  document.getElementById("svc-filter-note").textContent = `(${mNote}${sNote})`;
  if (!ms.length || !activeSubs.length) {
    document.getElementById("svc-table").innerHTML = "<p class='no-sel'>Keine Monate/Abos ausgew\u00e4hlt.</p>";
    return;
  }
  const hasDelta = n >= 2;
  const mLast = ms[n - 1], mPrev = ms[n - 2];
  let html = "<table class='svc-tbl'><thead><tr><th>Service</th>";
  ms.forEach(m => { html += `<th class="r">${ml(m)}</th>`; });
  html += '<th class="r">Gesamt</th>';
  if (hasDelta) {
    html += `<th class="r">\u0394\u00a0${ml(mPrev)}\u2192${ml(mLast)}\u00a0(\u20ac)</th>`;
    html += '<th class="r">\u0394\u00a0%</th>';
  }
  html += "</tr></thead><tbody>";
  DATA.svcList.forEach(svc => {
    const rowTot = svcCost(svc, ms);
    if (rowTot < 0.005) return;
    html += `<tr><td class="svc-name">${svc}</td>`;
    ms.forEach(m => { html += `<td class="r">${eur(svcCost(svc, [m]))}</td>`; });
    html += `<td class="r"><strong>${eur(rowTot)}</strong></td>`;
    if (hasDelta) {
      const vl = svcCost(svc, [mLast]);
      const vp = svcCost(svc, [mPrev]);
      const d  = vl - vp;
      const cls = d > 0 ? "up" : d < 0 ? "dn" : "nd";
      html += `<td class="r ${cls}">${eurSign(d)}</td>`;
      if (vp > 0) {
        const pct  = d / vp * 100;
        const pStr = `${(pct >= 0 ? "+" : "")}${pct.toFixed(1)}\u00a0%`;
        html += `<td class="r ${cls}">${Math.abs(pct) >= 20 ? "<strong>" : ""}${pStr}${Math.abs(pct) >= 20 ? "</strong>" : ""}</td>`;
      } else if (vl === 0) {
        html += "<td class='r nd'>\u2013</td>";
      } else {
        html += "<td class='r nd'>neu</td>";
      }
    }
    html += "</tr>";
  });
  const grandSvcTot = DATA.svcList.reduce((s, v) => s + svcCost(v, ms), 0);
  html += "<tr class='tot'><td>GESAMT</td>";
  ms.forEach(m => {
    const colTot = DATA.svcList.reduce((s, v) => s + svcCost(v, [m]), 0);
    html += `<td class="r">${eur(colTot)}</td>`;
  });
  html += `<td class="r">${eur(grandSvcTot)}</td>`;
  if (hasDelta) {
    const tl  = DATA.svcList.reduce((s, v) => s + svcCost(v, [mLast]), 0);
    const tp  = DATA.svcList.reduce((s, v) => s + svcCost(v, [mPrev]), 0);
    const td  = tl - tp;
    const cls = td > 0 ? "up" : td < 0 ? "dn" : "nd";
    html += `<td class="r ${cls}">${eurSign(td)}</td>`;
    if (tp > 0) {
      const pct = td / tp * 100;
      html += `<td class="r ${cls}">${(pct >= 0 ? "+" : "")}${pct.toFixed(1)}\u00a0%</td>`;
    } else {
      html += "<td class='r nd'>\u2013</td>";
    }
  }
  html += "</tr></tbody></table>";
  document.getElementById("svc-table").innerHTML = html;
}

// ── Render all ────────────────────────────────────────────────────────────────
function renderAll() {
  renderMonthBtns();
  renderSubBtns();
  renderSummary();
  drawChart();
  renderSubTable();
  renderSvcTable();
}

let _resizeTimer;
window.addEventListener("resize", () => { clearTimeout(_resizeTimer); _resizeTimer = setTimeout(drawChart, 120); });
renderAll();
"""


def build_html(
    output_file: str,
    monthly_records: list[dict],
    resource_totals: list[dict],
    sub_totals: list[dict],
    date_from: str,
    date_to: str,
) -> None:

    subs = [s["SubscriptionName"] for s in sub_totals]
    grand_total = sum(s["TotalCost"] for s in sub_totals)
    generated = datetime.now().strftime("%d.%m.%Y %H:%M")

    pivot: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for r in monthly_records:
        pivot[r.get("SubscriptionName", "")][r.get("Period", "")] += float(r.get("Cost", 0))

    svc_pivot: dict[str, dict[str, dict[str, float]]] = \
        defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    for r in monthly_records:
        sub = r.get("SubscriptionName", "")
        svc = r.get("ServiceName") or "Sonstige"
        m   = r.get("Period", "")
        if m and sub:
            svc_pivot[sub][svc][m] += float(r.get("Cost", 0))

    all_months = sorted({r.get("Period", "") for r in monthly_records if r.get("Period")})
    _svc_totals: dict[str, float] = defaultdict(float)
    for _sub_d in svc_pivot.values():
        for _svc, _md in _sub_d.items():
            _svc_totals[_svc] += sum(_md.values())
    svc_list = sorted(_svc_totals, key=lambda s: -_svc_totals[s])

    raw_json = json.dumps({
        "months": all_months,
        "subs": subs,
        "pivot": {s: dict(d) for s, d in pivot.items()},
        "svcList": svc_list,
        "svcPivot": {sub: {svc: dict(md) for svc, md in sub_d.items()}
                     for sub, sub_d in svc_pivot.items()},
    }, ensure_ascii=False)
    safe_json = raw_json.replace("</", "<\\/")
    js = _JS.replace("__DATA_JSON__", safe_json)

    sub_rows_html = ""
    for s in sub_totals:
        sub_rows_html += (
            f"<tr>"
            f"<td>{_esc(s['SubscriptionName'])}</td>"
            f"<td class='r'>{_eur(s['TotalCost'])}</td>"
            f"<td class='r'>{_esc(s.get('Currency', 'EUR'))}</td>"
            f"<td class='r'>{s['ResourceCount']}</td>"
            f"</tr>\n"
        )
    sub_rows_html += (
        f"<tr class='tot'>"
        f"<td>GESAMT</td>"
        f"<td class='r'>{_eur(grand_total)}</td>"
        f"<td class='r'>EUR</td>"
        f"<td class='r'>{sum(s['ResourceCount'] for s in sub_totals)}</td>"
        f"</tr>\n"
    )

    years = sorted({m[:4] for m in all_months})
    year_btns = " ".join(
        f"<button class=\"q-btn\" onclick=\"selectYear('{y}')\">{y}</button>"
        for y in years
    )

    html_out = f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Azure Cost Center Report</title>
  <style>{_CSS}</style>
</head>
<body>

<div class="hdr">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px">
    <div>
      <h1>&#9729; Azure Cost Center Report</h1>
      <div class="meta">Zeitraum: {_esc(date_from)} &ndash; {_esc(date_to)}&nbsp;&nbsp;|&nbsp;&nbsp;Erstellt: {_esc(generated)}</div>
    </div>
    <button class="btn-print" onclick="window.print()">&#128438;&nbsp; Drucken</button>
  </div>
</div>

<div class="wrap">

  <!-- Gesamtübersicht (statisch – voller Zeitraum) -->
  <div class="sec sec-sub">
    <h2>Gesamtkosten je Subscription (gesamter Zeitraum)</h2>
    <table>
      <thead><tr>
        <th>Subscription</th>
        <th class="r">Gesamtkosten</th>
        <th class="r">W&auml;hrung</th>
        <th class="r">Ressourcen</th>
      </tr></thead>
      <tbody>{sub_rows_html}</tbody>
    </table>
  </div>

  <!-- Monatsfilter -->
  <div class="sec sec-filter">
    <h2>&#128197; Monatsauswahl</h2>
    <div class="q-btns" style="margin-bottom:14px">
      <button class="q-btn q-btn-primary" onclick="selectAll()">Alle</button>
      <button class="q-btn" onclick="selectLast(3)">Letzte&nbsp;3</button>
      <button class="q-btn" onclick="selectLast(6)">Letzte&nbsp;6</button>
      <button class="q-btn" onclick="selectLast(12)">Letzte&nbsp;12</button>
      {year_btns}
      <button class="q-btn q-btn-danger" onclick="clearSel()">Keine</button>
    </div>
    <div id="month-btns"></div>
  </div>

  <!-- Subscription-Filter -->
  <div class="sec sec-filter">
    <h2>&#128290; Subscription-Auswahl</h2>
    <div class="q-btns" style="margin-bottom:14px">
      <button class="q-btn q-btn-primary" onclick="selectAllSubs()">Alle</button>
      <button class="q-btn q-btn-danger" onclick="clearSelSubs()">Keine</button>
    </div>
    <div id="sub-btns"></div>
  </div>

  <!-- Summary Cards (dynamisch) -->
  <div id="summary-cards"></div>

  <!-- Chart -->
  <div class="sec sec-chart">
    <h2>Monatliche Kostenentwicklung</h2>
    <div class="legend">
      <span><span class="dot" style="background:#2e75b6"></span>Erster Monat / unver&auml;ndert</span>
      <span><span class="dot" style="background:#c0392b"></span>Gestiegen</span>
      <span><span class="dot" style="background:#27ae60"></span>Gesunken</span>
    </div>
    <canvas id="chart" style="width:100%;display:block"></canvas>
  </div>

  <!-- Monatliche Kosten je Subscription (dynamisch) -->
  <div class="sec">
    <h2>Monatliche Kosten je Subscription <span class="filter-note" id="sub-filter-note"></span></h2>
    <div style="overflow-x:auto" id="sub-table"></div>
  </div>

  <!-- Service-Pivot (dynamisch) -->
  <div class="sec">
    <h2>Kosten je Azure-Service und Monat <span class="filter-note" id="svc-filter-note"></span></h2>
    <div style="overflow-x:auto" id="svc-table"></div>
  </div>

</div>

<script>{js}</script>
</body>
</html>"""

    Path(output_file).write_text(html_out, encoding="utf-8")
