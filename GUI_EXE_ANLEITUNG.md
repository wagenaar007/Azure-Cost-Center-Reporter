# Azure CostCenter Reporter – GUI & EXE-Build

**Ziel:** Keine Python-Installation beim Endnutzer nötig.  
Einzige Datei: `CostCenter.exe` – starten, Felder ausfüllen, Report klicken.

---

## Technologie-Vergleich

| Option | Dateigröße | Aufwand | Python nötig | Empfehlung |
|---|---|---|---|---|
| **PyInstaller + CustomTkinter** | ~60 MB | ★★☆ | ❌ | ✅ **Empfohlen** |
| Nuitka (nativ kompiliert) | ~20 MB | ★★★ | ❌ | Nur wenn Größe kritisch |
| .NET WinForms + Python.NET | ~15 MB | ★★★★ | ❌ | Zu komplex |
| Electron/Tauri | >100 MB | ★★★★ | ❌ | Zu groß |
| Portable Python (eingebettet) | ~40 MB | ★★☆ | ❌ | Alternative |

### Warum PyInstaller + CustomTkinter?

- **CustomTkinter**: modernes, dunkles GUI-Design (nicht das alte Tkinter-Look)
- **PyInstaller `--onefile`**: alles in einer einzigen `.exe` gebündelt
- Kein Python, keine Module, kein pip auf dem Ziel-PC nötig
- Funktioniert auf Windows 10/11 ohne Installation
- Einstellungen werden lokal in `costcenter_settings.json` gespeichert

---

## Was die GUI macht

```
┌─────────────────────────────────────────────────────────┐
│  Azure Cost Center Reporter  v1.0                       │
├─────────────────────────────┬───────────────────────────┤
│  Konfiguration (scrollbar)  │  Protokoll                │
│                             │                           │
│  ── Azure Auth ──           │  12:05:01  INFO  Token OK │
│  Tenant ID      [_______]   │  12:05:02  INFO  Chunk... │
│  Client ID      [_______]   │  12:06:10  INFO  11959... │
│  Client Secret  [•••••••]   │  ...                      │
│                             │                           │
│  ── Subscriptions ──        │                           │
│  Sub 1  [ID] [Name]         │                           │
│  Sub 2  [ID] [Name]         │                           │
│  Sub 3  [ID] [Name]         │                           │
│  Sub 4  [ID] [Name]         │                           │
│                             │                           │
│  ── Zeitraum ──             │  [Log leeren]  [Speichern]│
│  Von [2025-01-01]           │                           │
│  Bis [2026-05-21]           │  ✅ Fertig!               │
│                             │                           │
│  ── Output ──               │  [📊 Excel öffnen]        │
│  Datei [Report.xlsx] [📁]   │                           │
│                             │                           │
│  [Speichern]  [▶ Starten]   │                           │
└─────────────────────────────┴───────────────────────────┘
```

**Features:**
- ✅ Alle `.env`-Felder als Eingabefelder
- ✅ Client Secret wird verschleiert angezeigt (●●●●●)
- ✅ Einstellungen werden in `costcenter_settings.json` gespeichert und beim nächsten Start geladen
- ✅ Log-Ausgabe in Echtzeit im Fenster (kein schwarzes Konsolenfenster)
- ✅ Button „Excel öffnen" erscheint nach erfolgreichem Abschluss
- ✅ Mehrfach ausführbar ohne Neustart (neue Zeiträume, andere Subscriptions etc.)

---

## Voraussetzungen (einmalig auf dem Build-PC)

```powershell
# Python muss installiert sein (nur auf dem Build-PC!)
pip install customtkinter pyinstaller

# Oder alle auf einmal:
pip install -r requirements.txt
```

---

## EXE bauen

```powershell
# Im Projektordner ausführen:
.\build_exe.ps1
```

Das Skript:
1. Installiert fehlende Dependencies
2. Ruft PyInstaller auf
3. Die fertige `.exe` liegt in: `dist\CostCenter.exe`

**Buildzeit:** ca. 1–3 Minuten

---

## Verteilung

Für den Endnutzer wird **nur eine Datei** benötigt:

```
CostCenter.exe          ← die fertige EXE
```

Optional (empfohlen) als ZIP-Paket bereitstellen:
```
CostCenter_v1.zip
  └── CostCenter.exe
```

Beim ersten Start legt die App automatisch an:
```
costcenter_settings.json    ← gespeicherte Einstellungen (im selben Ordner wie .exe)
```

> **Hinweis:** `costcenter_settings.json` enthält die Credentials (base64-verschleiert).  
> Die Datei sollte nicht weitergegeben werden.

---

## Ablauf beim Endnutzer

1. `CostCenter.exe` starten (Doppelklick)
2. Felder ausfüllen (beim zweiten Mal: automatisch vorausgefüllt)
3. **„▶ Report erstellen"** klicken
4. Fortschritt im Protokoll-Bereich beobachten
5. Nach ca. 20–30 Minuten: **„📊 Excel öffnen"** klicken

---

## Alternative: Portable Python (ohne Build)

Falls kein Build gewünscht:

1. Python Embeddable Package herunterladen: [python.org/downloads](https://www.python.org/downloads/)
2. Alle Projektdateien + `python-embed/` in einen Ordner
3. `start.bat` erstellen:
   ```bat
   @echo off
   python-embed\python.exe run.py
   pause
   ```
4. Den ganzen Ordner als ZIP weitergeben (~25 MB)

**Nachteil:** Kein GUI, läuft in Konsole. Für technische Nutzer OK.
