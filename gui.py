import os
import sys
import time
import json
import queue
import logging
import threading
from datetime import datetime
from pathlib import Path

import customtkinter as ctk
from tkinter import filedialog, messagebox

if getattr(sys, "frozen", False):
    _BASE = Path(sys._MEIPASS)
    _APP_DIR = Path(sys.executable).parent
else:
    _BASE = Path(__file__).parent
    _APP_DIR = _BASE

sys.path.insert(0, str(_BASE))
SETTINGS_FILE = _APP_DIR / "costcenter_settings.json"


class _GUILogHandler(logging.Handler):
    def __init__(self, q: queue.Queue):
        super().__init__()
        self.queue = q

    def emit(self, record: logging.LogRecord):
        self.queue.put((record.levelno, self.format(record)))


class CostCenterApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("Azure Cost Center Reporter  v0.0.2")
        self.geometry("1060x760")
        self.minsize(860, 620)

        self._log_queue: queue.Queue = queue.Queue()
        self._excel_path: str | None = None
        self._html_path: str | None = None
        self._running = False
        self._progress_val = 0.0
        self._available_subs: list[dict] = []
        self._sub_checks: dict[str, ctk.BooleanVar] = {}

        self._build_ui()
        self._load_settings()
        self._poll_log()


    _HDR  = "#0A1929"
    _SURF = "#0D1B2E"
    _CARD = "#162640"
    _BDR  = "#1E3D5C"
    _ACC  = "#4DA8D4"
    _ACC2 = "#1E6EA8"
    _T1   = "#E8F0FE"
    _T2   = "#7A9ABB"


    def _build_ui(self):
        self.configure(fg_color=self._SURF)

        hdr = ctk.CTkFrame(self, height=64, corner_radius=0, fg_color=self._HDR)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        left = ctk.CTkFrame(hdr, fg_color="transparent")
        left.pack(side="left", padx=18, pady=10)
        ctk.CTkLabel(left, text="☁", font=ctk.CTkFont(size=30),
                     text_color=self._ACC).pack(side="left", padx=(0, 10))
        txt = ctk.CTkFrame(left, fg_color="transparent")
        txt.pack(side="left")
        ctk.CTkLabel(txt, text="Azure Cost Center Reporter",
                     font=ctk.CTkFont(size=17, weight="bold"),
                     text_color=self._T1).pack(anchor="w")
        ctk.CTkLabel(txt, text="Cost transparency & Excel reports for Azure Subscriptions",
                     font=ctk.CTkFont(size=10),
                     text_color=self._T2).pack(anchor="w")

        badge = ctk.CTkFrame(hdr, fg_color=self._ACC2, corner_radius=6)
        badge.pack(side="right", padx=18, pady=20)
        ctk.CTkLabel(badge, text="v 0.0.2", font=ctk.CTkFont(size=10),
                     text_color="white").pack(padx=10, pady=3)

        ctk.CTkFrame(self, height=1, fg_color=self._BDR).pack(fill="x")

        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=14, pady=10)
        main.grid_columnconfigure(0, weight=45)
        main.grid_columnconfigure(1, weight=55)
        main.grid_rowconfigure(0, weight=1)

        cfg = ctk.CTkScrollableFrame(
            main, fg_color=self._SURF, corner_radius=10,
            scrollbar_fg_color=self._SURF,
            scrollbar_button_color=self._BDR,
            scrollbar_button_hover_color=self._ACC2,
        )
        cfg.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        ctk.CTkLabel(cfg, text="CONFIGURATION",
                     font=ctk.CTkFont(size=9, weight="bold"),
                     text_color=self._T2).pack(anchor="w", padx=14, pady=(12, 2))
        ctk.CTkFrame(cfg, height=1, fg_color=self._BDR).pack(fill="x", padx=10, pady=(0, 8))
        self._build_form(cfg)

        rgt = ctk.CTkFrame(main, fg_color=self._SURF, corner_radius=10)
        rgt.grid(row=0, column=1, sticky="nsew")
        self._build_log(rgt)

        self._build_statusbar()

    def _card(self, parent, title: str) -> ctk.CTkFrame:
        outer = ctk.CTkFrame(parent, fg_color=self._CARD, corner_radius=8,
                              border_width=1, border_color=self._BDR)
        outer.pack(fill="x", padx=10, pady=(0, 10))
        hf = ctk.CTkFrame(outer, fg_color="transparent")
        hf.pack(fill="x", padx=12, pady=(8, 0))
        ctk.CTkLabel(hf, text=title,
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=self._ACC).pack(anchor="w")
        ctk.CTkFrame(outer, height=1, fg_color=self._BDR).pack(fill="x", padx=8, pady=(6, 0))
        body = ctk.CTkFrame(outer, fg_color="transparent")
        body.pack(fill="x", padx=12, pady=(6, 12))
        return body

    def _field(self, parent, label: str, placeholder: str = "",
               show: str | None = None) -> ctk.CTkEntry:
        ctk.CTkLabel(parent, text=label, font=ctk.CTkFont(size=11),
                     text_color=self._T2).pack(anchor="w", pady=(4, 1))
        kw: dict = {"placeholder_text": placeholder,
                    "fg_color": self._SURF,
                    "border_color": self._BDR, "border_width": 1,
                    "text_color": self._T1,
                    "placeholder_text_color": "#3A5A7A"}
        if show:
            kw["show"] = show
        e = ctk.CTkEntry(parent, **kw)
        e.pack(fill="x", pady=(0, 6))
        return e


    def _build_form(self, p):
        auth = self._card(p, "🔑  Azure Authentication")
        self.e_tenant = self._field(auth, "Tenant ID", "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
        self.e_client = self._field(auth, "Client ID", "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
        self.e_secret = self._field(auth, "Client Secret", "Your secret value", show="●")

        sub = self._card(p, "☁  Subscriptions")
        btn_row = ctk.CTkFrame(sub, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, 6))
        self.btn_load_subs = ctk.CTkButton(
            btn_row, text="🔍  Load", height=30, width=130,
            fg_color=self._ACC2, hover_color=self._ACC,
            font=ctk.CTkFont(size=11), text_color="white",
            command=self._load_subscriptions,
        )
        self.btn_load_subs.pack(side="left")
        ctk.CTkButton(
            btn_row, text="All", height=30, width=46,
            fg_color=self._CARD, hover_color=self._BDR,
            border_width=1, border_color=self._BDR,
            font=ctk.CTkFont(size=10), text_color=self._T1,
            command=self._subs_select_all,
        ).pack(side="left", padx=(6, 0))
        ctk.CTkButton(
            btn_row, text="None", height=30, width=46,
            fg_color=self._CARD, hover_color=self._BDR,
            border_width=1, border_color=self._BDR,
            font=ctk.CTkFont(size=10), text_color=self._T1,
            command=self._subs_select_none,
        ).pack(side="left", padx=(4, 0))

        self.lbl_sub_status = ctk.CTkLabel(
            sub, text="No subscriptions loaded yet.",
            font=ctk.CTkFont(size=10), text_color=self._T2,
        )
        self.lbl_sub_status.pack(anchor="w", pady=(0, 4))

        self.sub_check_frame = ctk.CTkScrollableFrame(
            sub, fg_color=self._SURF, corner_radius=6,
            border_width=1, border_color=self._BDR, height=130,
            scrollbar_fg_color=self._SURF,
            scrollbar_button_color=self._BDR,
            scrollbar_button_hover_color=self._ACC2,
        )
        self.sub_check_frame.pack(fill="x")

        zt = self._card(p, "\U0001f4c5  Date Range")
        drow = ctk.CTkFrame(zt, fg_color="transparent")
        drow.pack(fill="x")
        drow.grid_columnconfigure(0, weight=1)
        drow.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(drow, text="From (YYYY-MM-DD)", font=ctk.CTkFont(size=11),
                     text_color=self._T2).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(drow, text="To (YYYY-MM-DD)", font=ctk.CTkFont(size=11),
                     text_color=self._T2).grid(row=0, column=1, sticky="w", padx=(10, 0))
        self.e_date_from = ctk.CTkEntry(
            drow, placeholder_text="2025-01-01",
            fg_color=self._SURF, border_color=self._BDR, border_width=1, text_color=self._T1)
        self.e_date_from.grid(row=1, column=0, sticky="ew", pady=(2, 0))
        self.e_date_to = ctk.CTkEntry(
            drow, placeholder_text=datetime.now().strftime("%Y-%m-%d"),
            fg_color=self._SURF, border_color=self._BDR, border_width=1, text_color=self._T1)
        self.e_date_to.grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=(2, 0))

        out = self._card(p, "📁  Excel Output")
        orow = ctk.CTkFrame(out, fg_color="transparent")
        orow.pack(fill="x")
        orow.grid_columnconfigure(0, weight=1)
        self.e_output = ctk.CTkEntry(
            orow, placeholder_text="CostCenter_Report.xlsx",
            fg_color=self._SURF, border_color=self._BDR, border_width=1, text_color=self._T1)
        self.e_output.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(orow, text="…", width=36, height=28,
                      fg_color=self._ACC2, hover_color=self._ACC,
                      command=self._browse_output).grid(row=0, column=1)

        pub = self._card(p, "\u2601  Publish to Azure")
        self.e_storage_account   = self._field(pub, "Storage Account Name", "z.B. costcenterreports")
        self.e_storage_container = self._field(pub, "Container Name", "reports")
        self.e_storage_web_url   = self._field(pub, "Web Endpoint URL", "https://<account>.z6.web.core.windows.net")
        self.e_storage_msal_client = self._field(pub, "MSAL Client ID (f\u00fcr Index-Login)", "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
        ctk.CTkLabel(pub, text="Web Endpoint URL: Static Website Endpunkt aus dem Azure Portal (Datenverwaltung \u2192 Statische Website).",
                     font=ctk.CTkFont(size=9), text_color="#3A5A7A").pack(anchor="w", pady=(0, 4))

        ctk.CTkFrame(p, height=1, fg_color=self._BDR).pack(fill="x", padx=10, pady=(10, 8))
        brow = ctk.CTkFrame(p, fg_color="transparent")
        brow.pack(fill="x", padx=10, pady=(0, 8))
        ctk.CTkButton(
            brow, text="\U0001f4be  Save", height=34, width=118,
            fg_color=self._CARD, hover_color=self._BDR,
            border_width=1, border_color=self._ACC2,
            font=ctk.CTkFont(size=11), text_color=self._T1,
            command=self._save_settings
        ).pack(side="left")
        ctk.CTkButton(
            brow, text="\U0001f5d1  Clear Cache", height=34, width=110,
            fg_color="#2A0E0E", hover_color="#441A1A",
            border_width=1, border_color="#6B2626",
            font=ctk.CTkFont(size=11), text_color="#FF9090",
            command=self._clear_cache
        ).pack(side="left", padx=(6, 0))
        self.btn_publish = ctk.CTkButton(
            brow, text="\u2601  Ver\u00f6ffentlichen", height=34, width=148,
            fg_color="#0B3050", hover_color="#1A4F78",
            border_width=1, border_color="#1E6EA8",
            font=ctk.CTkFont(size=11, weight="bold"), text_color="#7DC4E8",
            state="disabled",
            command=self._publish_reports
        )
        self.btn_publish.pack(side="right", padx=(6, 0))
        self.btn_start = ctk.CTkButton(
            brow, text="\u25b6  Create Report", height=34, width=148,
            fg_color="#0B4A26", hover_color="#136635",
            border_width=1, border_color="#1A8040",
            font=ctk.CTkFont(size=12, weight="bold"), text_color="#90FFB8",
            command=self._start
        )
        self.btn_start.pack(side="right")


    def _load_subscriptions(self):
        tenant = self.e_tenant.get().strip()
        client = self.e_client.get().strip()
        secret = self.e_secret.get().strip()
        if not all([tenant, client, secret]):
            messagebox.showwarning(
                "Missing credentials",
                "Please fill in Tenant ID, Client ID and Client Secret first.",
            )
            return
        self.btn_load_subs.configure(state="disabled", text="⏳  Loading…")
        self.lbl_sub_status.configure(text="Loading subscriptions…",
                                      text_color=self._T2)

        def _fetch():
            try:
                from azure.identity import ClientSecretCredential
                from src.subscription_client import list_subscriptions
                cred  = ClientSecretCredential(tenant, client, secret)
                token = cred.get_token("https://management.azure.com/.default").token
                subs  = list_subscriptions(token)
                self.after(0, lambda: self._populate_sub_checkboxes(subs))
            except Exception as exc:
                self.after(0, lambda e=exc: self._on_subs_load_error(e))

        threading.Thread(target=_fetch, daemon=True).start()

    def _on_subs_load_error(self, exc: Exception):
        self.btn_load_subs.configure(state="normal", text="\U0001f50d  Load")
        self.lbl_sub_status.configure(
            text=f"Error loading: {exc}", text_color="#E05050"
        )

    def _populate_sub_checkboxes(self, subs: list[dict],
                                  preselect: set[str] | None = None):
        for w in self.sub_check_frame.winfo_children():
            w.destroy()
        self._sub_checks.clear()
        self._available_subs = subs
        if preselect is None:
            preselect = {s["id"] for s in subs if s["state"] == "Enabled"}
        for s in subs:
            var = ctk.BooleanVar(value=(s["id"] in preselect))
            self._sub_checks[s["id"]] = var
            label = s["name"] if s["state"] == "Enabled" else f"{s['name']}  ⚠ disabled"
            cb = ctk.CTkCheckBox(
                self.sub_check_frame,
                text=label,
                variable=var,
                font=ctk.CTkFont(size=11),
                text_color=self._T1 if s["state"] == "Enabled" else "#E6A020",
                fg_color=self._ACC2,
                hover_color=self._ACC,
                border_color=self._BDR,
                command=self._update_sub_status,
            )
            cb.pack(anchor="w", pady=2)
        self.btn_load_subs.configure(state="normal", text="🔄  Refresh")
        self._update_sub_status()

    def _update_sub_status(self):
        total    = len(self._sub_checks)
        selected = sum(1 for v in self._sub_checks.values() if v.get())
        if total == 0:
            self.lbl_sub_status.configure(
                text="No subscriptions loaded yet.", text_color=self._T2
            )
        else:
            col = "#4EC98A" if selected > 0 else "#E05050"
            self.lbl_sub_status.configure(
                text=f"{selected} of {total} subscription(s) selected",
                text_color=col,
            )

    def _subs_select_all(self):
        for v in self._sub_checks.values():
            v.set(True)
        self._update_sub_status()

    def _subs_select_none(self):
        for v in self._sub_checks.values():
            v.set(False)
        self._update_sub_status()


    def _build_log(self, p):
        p.grid_rowconfigure(2, weight=1)
        p.grid_columnconfigure(0, weight=1)

        lhdr = ctk.CTkFrame(p, fg_color="transparent")
        lhdr.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 0))
        ctk.CTkLabel(lhdr, text="LOG",
                     font=ctk.CTkFont(size=9, weight="bold"),
                     text_color=self._T2).pack(side="left")
        self.btn_open = ctk.CTkButton(
            lhdr, text="\U0001f4ca Open Excel", state="disabled",
            height=28, width=130, font=ctk.CTkFont(size=10),
            fg_color=self._ACC2, hover_color=self._ACC, text_color="white",
            command=self._open_excel
        )
        self.btn_open.pack(side="right")
        self.btn_browser = ctk.CTkButton(
            lhdr, text="\U0001f310 Open in Browser", state="disabled",
            height=28, width=118, font=ctk.CTkFont(size=10),
            fg_color="#174A6B", hover_color=self._ACC2, text_color="white",
            command=self._open_browser
        )
        self.btn_browser.pack(side="right", padx=(0, 6))
        ctk.CTkButton(
            lhdr, text="🗑", width=30, height=28,
            fg_color=self._CARD, hover_color=self._BDR, text_color=self._T2,
            command=self._clear_log
        ).pack(side="right", padx=(0, 6))

        ctk.CTkFrame(p, height=1, fg_color=self._BDR).grid(
            row=1, column=0, sticky="ew", padx=10, pady=(6, 0))

        self.log_box = ctk.CTkTextbox(
            p, font=ctk.CTkFont(family="Consolas", size=10),
            state="disabled", wrap="word", fg_color="#080F1A",
            border_width=1, border_color=self._BDR, corner_radius=6
        )
        self.log_box.grid(row=2, column=0, sticky="nsew", padx=12, pady=8)
        tb = self.log_box._textbox
        tb.tag_configure("info",    foreground="#7A9ABB")
        tb.tag_configure("success", foreground="#4EC98A")
        tb.tag_configure("warning", foreground="#E6A020")
        tb.tag_configure("error",   foreground="#E05050")
        tb.tag_configure("ts",      foreground="#3A5A7A")

    def _build_statusbar(self):
        bar = ctk.CTkFrame(self, height=36, corner_radius=0, fg_color=self._HDR)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        ctk.CTkFrame(self, height=1, fg_color=self._BDR).pack(fill="x", side="bottom")

        self.lbl_status = ctk.CTkLabel(
            bar, text="\u25cf Ready", font=ctk.CTkFont(size=10),
            text_color=self._T2
        )
        self.lbl_status.pack(side="left", padx=14)

        ctk.CTkLabel(
            bar, text="\u00a9 2026 Azure CostCenter Reporter Contributors  \u2022  v0.0.2",
            font=ctk.CTkFont(size=9), text_color="#3A5A7A"
        ).pack(side="right", padx=14)

        self.progress = ctk.CTkProgressBar(
            bar, height=6, corner_radius=3,
            fg_color=self._CARD, progress_color=self._ACC, width=220
        )
        self.progress.set(0)
        self.progress.pack(side="right", padx=14)


    def _get_config(self) -> dict:
        checked = [
            (sid, next((s["name"] for s in self._available_subs if s["id"] == sid), sid))
            for sid, var in self._sub_checks.items() if var.get()
        ]
        ids   = [c[0] for c in checked]
        names = [c[1] for c in checked]
        return {
            "TENANT_ID":          self.e_tenant.get().strip(),
            "CLIENT_ID":          self.e_client.get().strip(),
            "CLIENT_SECRET":      self.e_secret.get().strip(),
            "SUBSCRIPTION_IDS":   ",".join(ids),
            "SUBSCRIPTION_NAMES": ",".join(names),
            "DATE_FROM":          self.e_date_from.get().strip() or "2025-01-01",
            "DATE_TO":            self.e_date_to.get().strip() or datetime.now().strftime("%Y-%m-%d"),
            "OUTPUT_FILE":        self.e_output.get().strip() or "CostCenter_Report.xlsx",
        }

    def _clear_cache(self):
        from tkinter import messagebox
        if not messagebox.askyesno(
            "Cache löschen",
            "Alle lokal gespeicherten Kostendaten löschen?\n\n"
            "Beim nächsten Report werden alle Monate neu von der Azure API abgerufen.",
        ):
            return
        try:
            from src.cache import init_db, clear_cache, get_cache_summary
            init_db()
            info = get_cache_summary()
            months_total = sum(c["months_cached"] for c in info) if info else 0
            clear_cache()
            self._append_log(
                f"Cache gelöscht – {months_total} Monat(e) entfernt. "
                "Alle Daten werden beim nächsten Report neu abgerufen.",
                logging.INFO,
            )
        except Exception as exc:
            self._append_log(f"Cache löschen fehlgeschlagen: {exc}", logging.ERROR)

    def _save_settings(self):
        import base64
        cfg = self._get_config()
        save = dict(cfg)
        if save.get("CLIENT_SECRET"):
            save["CLIENT_SECRET"] = base64.b64encode(
                save["CLIENT_SECRET"].encode()
            ).decode()
            save["_secret_b64"] = True
        save["_available_subs"]      = self._available_subs
        save["STORAGE_ACCOUNT"]      = self.e_storage_account.get().strip()
        save["STORAGE_CONTAINER"]    = self.e_storage_container.get().strip()
        save["STORAGE_WEB_URL"]      = self.e_storage_web_url.get().strip()
        save["STORAGE_MSAL_CLIENT"]  = self.e_storage_msal_client.get().strip()
        try:
            SETTINGS_FILE.write_text(json.dumps(save, indent=2, ensure_ascii=False), encoding="utf-8")
            self._append_log("Settings saved.", logging.INFO)
        except Exception as exc:
            self._append_log(f"Failed to save settings: {exc}", logging.ERROR)

    def _load_settings(self):
        if not SETTINGS_FILE.exists():
            return
        try:
            import base64
            data: dict = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            if data.get("_secret_b64") and data.get("CLIENT_SECRET"):
                data["CLIENT_SECRET"] = base64.b64decode(data["CLIENT_SECRET"]).decode()

            def _fill(entry: ctk.CTkEntry, key: str):
                v = data.get(key, "")
                if v:
                    entry.delete(0, "end")
                    entry.insert(0, v)

            _fill(self.e_tenant,    "TENANT_ID")
            _fill(self.e_client,    "CLIENT_ID")
            _fill(self.e_secret,    "CLIENT_SECRET")
            _fill(self.e_date_from, "DATE_FROM")
            _fill(self.e_date_to,   "DATE_TO")
            _fill(self.e_output,    "OUTPUT_FILE")

            saved_subs  = data.get("_available_subs", [])
            checked_ids = {s.strip() for s in data.get("SUBSCRIPTION_IDS", "").split(",") if s.strip()}
            if saved_subs:
                self._populate_sub_checkboxes(saved_subs, preselect=checked_ids)

            def _fill_pub(entry: ctk.CTkEntry, key: str):
                v = data.get(key, "")
                if v:
                    entry.delete(0, "end")
                    entry.insert(0, v)

            _fill_pub(self.e_storage_account,     "STORAGE_ACCOUNT")
            _fill_pub(self.e_storage_container,   "STORAGE_CONTAINER")
            _fill_pub(self.e_storage_web_url,     "STORAGE_WEB_URL")
            _fill_pub(self.e_storage_msal_client, "STORAGE_MSAL_CLIENT")
        except Exception as exc:
            self._append_log(f"Could not load settings: {exc}", logging.WARNING)

    def _browse_output(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            initialfile="CostCenter_Report.xlsx",
            title="Save Excel report as",
        )
        if path:
            self.e_output.delete(0, "end")
            self.e_output.insert(0, path)


    def _start(self):
        if self._running:
            return

        cfg = self._get_config()
        missing = [k for k in ("TENANT_ID", "CLIENT_ID", "CLIENT_SECRET", "SUBSCRIPTION_IDS")
                   if not cfg.get(k)]
        if missing:
            messagebox.showerror(
                "Missing fields",
                f"The following required fields are missing:\n\n" + "\n".join(missing)
            )
            return

        self._running = True
        self._excel_path = None
        self.btn_start.configure(state="disabled", text="⏳  Running…")
        self.btn_open.configure(state="disabled")
        self.lbl_status.configure(text="⏳  Creating report…", text_color="#E6A020")
        self.progress.set(0)
        self._animate_progress()

        thread = threading.Thread(target=self._run_report, args=(cfg,), daemon=True)
        thread.start()

    def _animate_progress(self):
        if not self._running:
            return
        self._progress_val = (self._progress_val + 0.012) % 1.0
        self.progress.set(self._progress_val)
        self.after(80, self._animate_progress)

    def _run_report(self, cfg: dict):
        handler = _GUILogHandler(self._log_queue)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s  %(levelname)-8s  %(message)s", "%H:%M:%S"
        ))
        root_log = logging.getLogger()
        root_log.addHandler(handler)
        root_log.setLevel(logging.INFO)
        logging.getLogger("azure").setLevel(logging.WARNING)
        logging.getLogger("msal").setLevel(logging.WARNING)

        try:
            from azure.identity import ClientSecretCredential

            credential = ClientSecretCredential(
                tenant_id=cfg["TENANT_ID"],
                client_id=cfg["CLIENT_ID"],
                client_secret=cfg["CLIENT_SECRET"],
            )
            arm_token_fn = lambda: credential.get_token(
                "https://management.azure.com/.default"
            ).token

            from src.cache import init_db, get_cache_summary
            init_db()
            cache_info = get_cache_summary()
            if cache_info:
                cached_months_total = sum(c["months_cached"] for c in cache_info)
                self._log_queue.put((20, f"Cache: {cached_months_total} month(s) already cached \u2013 only new months will be fetched."))

            sub_ids   = [s.strip() for s in cfg["SUBSCRIPTION_IDS"].split(",")   if s.strip()]
            sub_names = [s.strip() for s in cfg["SUBSCRIPTION_NAMES"].split(",") if s.strip()]
            while len(sub_names) < len(sub_ids):
                sub_names.append(f"Subscription {len(sub_names) + 1}")

            date_from   = cfg["DATE_FROM"]
            date_to     = cfg["DATE_TO"]
            output_file = cfg["OUTPUT_FILE"]
            if not Path(output_file).is_absolute():
                output_file = str(_APP_DIR / output_file)

            from src.cost_client   import query_daily_costs
            from src               import aggregator
            from src.excel_builder import build_excel

            all_daily: list[dict] = []
            subs = list(zip(sub_ids, sub_names))
            for sub_id, sub_name in subs:
                records = query_daily_costs(arm_token_fn, sub_id, sub_name, date_from, date_to)
                all_daily.extend(records)

            weekly          = aggregator.aggregate_weekly(all_daily)
            monthly         = aggregator.aggregate_monthly(all_daily)
            yearly          = aggregator.aggregate_yearly(all_daily)
            resource_totals = aggregator.aggregate_resource_totals(all_daily)
            sub_totals      = aggregator.subscription_totals(resource_totals)

            build_excel(
                output_file=output_file,
                weekly_records=weekly,
                monthly_records=monthly,
                yearly_records=yearly,
                resource_totals=resource_totals,
                sub_totals=sub_totals,
                date_from=date_from,
                date_to=date_to,
            )

            self._excel_path = output_file

            html_path = str(Path(output_file).with_suffix(".html"))
            try:
                from src.html_builder import build_html as _build_html
                _build_html(
                    output_file=html_path,
                    monthly_records=monthly,
                    resource_totals=resource_totals,
                    sub_totals=sub_totals,
                    date_from=date_from,
                    date_to=date_to,
                    excel_filename=Path(output_file).name,
                )
                self._html_path = html_path
            except Exception as _html_exc:
                self._log_queue.put((30, f"HTML report skipped: {_html_exc}"))

            self._log_queue.put((-1, f"\u2705  Report saved: {output_file}"))

        except Exception as exc:
            import traceback
            self._log_queue.put((-2, f"{exc}\n{traceback.format_exc()}"))

        finally:
            for h in list(root_log.handlers):
                if isinstance(h, _GUILogHandler):
                    root_log.removeHandler(h)


    def _poll_log(self):
        try:
            while True:
                level, msg = self._log_queue.get_nowait()
                if level == -1:
                    self._append_log(msg, -1)
                    self._running = False
                    self.progress.set(1.0)
                    self.btn_start.configure(state="normal", text="\u25b6  Create Report")
                    self.btn_open.configure(state="normal")
                    if self._html_path:
                        self.btn_browser.configure(state="normal")
                        self.btn_publish.configure(state="normal")
                    self.lbl_status.configure(text="\u25cf  Done!", text_color="#4EC98A")
                elif level == -2:
                    self._append_log(f"ERROR: {msg}", logging.ERROR)
                    self._running = False
                    self.progress.set(0)
                    self.btn_start.configure(state="normal", text="\u25b6  Create Report")
                    self.lbl_status.configure(text="\u25cf  Error \u2013 see log",
                                               text_color="#E05050")
                else:
                    self._append_log(msg, level)
        except queue.Empty:
            pass
        self.after(200, self._poll_log)

    def _append_log(self, msg: str, level: int = logging.INFO):
        self.log_box.configure(state="normal")
        tb = self.log_box._textbox
        if level == -1 or (isinstance(msg, str) and msg.startswith("✅")):
            tag = "success"
        elif level == logging.WARNING:
            tag = "warning"
        elif level == logging.ERROR or level == -2:
            tag = "error"
        else:
            tag = "info"
        tb.insert("end", msg + "\n", tag)
        self.log_box.configure(state="disabled")
        self.log_box.see("end")

    def _clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def _open_excel(self):
        if self._excel_path and Path(self._excel_path).exists():
            os.startfile(self._excel_path)
        else:
            messagebox.showwarning("File not found",
                                   f"File not found:\n{self._excel_path}")

    def _open_browser(self):
        import webbrowser
        if self._html_path and Path(self._html_path).exists():
            webbrowser.open(Path(self._html_path).as_uri())
        else:
            messagebox.showwarning("File not found",
                                   f"HTML report not found:\n{self._html_path}")

    def _publish_reports(self):
        account   = self.e_storage_account.get().strip()
        container = self.e_storage_container.get().strip()
        web_url   = self.e_storage_web_url.get().strip().rstrip("/")
        msal_cid  = self.e_storage_msal_client.get().strip()
        cfg       = self._get_config()
        tenant_id    = cfg.get("TENANT_ID", "")
        client_id    = cfg.get("CLIENT_ID", "")
        client_secret = cfg.get("CLIENT_SECRET", "")

        if not all([account, container, web_url, tenant_id, client_id, client_secret]):
            messagebox.showerror(
                "Fehlende Einstellungen",
                "Bitte f\u00fclle alle Felder aus:\n"
                "  - Storage Account Name\n"
                "  - Container Name\n"
                "  - Web Endpoint URL\n"
                "  - Tenant ID, Client ID, Client Secret (aus Azure Authentication)"
            )
            return

        if not self._html_path or not Path(self._html_path).exists():
            messagebox.showerror("Kein Report", "Bitte zuerst einen Report erstellen.")
            return

        self.btn_publish.configure(state="disabled", text="\u23f3  Uploading\u2026")
        self.lbl_status.configure(text="\u23f3  Ver\u00f6ffentliche\u2026", text_color="#E6A020")

        files_to_upload = [self._html_path]
        if self._excel_path and Path(self._excel_path).exists():
            files_to_upload.append(self._excel_path)

        def _do_publish():
            try:
                from src.storage_client import upload_reports, list_blobs, upload_index, delete_tmp_blobs
                from src.index_builder  import build_index_html

                def _progress(msg):
                    self._log_queue.put((20, msg))

                # Clean up leftover tmp*.html blobs from old versions
                delete_tmp_blobs(account, container, tenant_id, client_id, client_secret)

                upload_reports(
                    account=account,
                    container=container,
                    tenant_id=tenant_id,
                    client_id=client_id,
                    client_secret=client_secret,
                    files=files_to_upload,
                    progress_cb=_progress,
                )

                # Rebuild index.html and upload to $web (Static Website root)
                blobs = list_blobs(account, container, tenant_id, client_id, client_secret)
                index_html = build_index_html(
                    blobs=blobs,
                    account=account,
                    container=container,
                    client_id=msal_cid or client_id,
                    tenant_id=tenant_id,
                )
                upload_index(
                    account=account,
                    tenant_id=tenant_id,
                    client_id=client_id,
                    client_secret=client_secret,
                    index_html=index_html,
                    progress_cb=_progress,
                )

                index_url = web_url
                self._log_queue.put((-1, f"\u2705  Ver\u00f6ffentlicht! Index: {index_url}"))
                self.after(0, lambda: self._on_publish_done(index_url))

            except Exception as exc:
                import traceback
                self._log_queue.put((-2, f"Publish fehlgeschlagen: {exc}\n{traceback.format_exc()}"))
                self.after(0, lambda: self.btn_publish.configure(
                    state="normal", text="\u2601  Ver\u00f6ffentlichen"
                ))

        threading.Thread(target=_do_publish, daemon=True).start()

    def _on_publish_done(self, index_url: str):
        import webbrowser
        self.btn_publish.configure(state="normal", text="\u2601  Ver\u00f6ffentlichen")
        self.lbl_status.configure(text="\u25cf  Ver\u00f6ffentlicht!", text_color="#4EC98A")
        if messagebox.askyesno(
            "Ver\u00f6ffentlicht!",
            f"Reports wurden erfolgreich hochgeladen.\n\n"
            f"Index-URL:\n{index_url}\n\n"
            "Im Browser \u00f6ffnen?"
        ):
            webbrowser.open(index_url)


if __name__ == "__main__":
    app = CostCenterApp()
    app.mainloop()
