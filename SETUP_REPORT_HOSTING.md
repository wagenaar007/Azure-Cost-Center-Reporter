# Report Hosting einrichten
### Azure CostCenter Reporter – Berichte in Azure veröffentlichen

> **Voraussetzung:** Der Service Principal aus `SETUP_SERVICE_PRINCIPAL.md` ist bereits
> eingerichtet. Du benötigst außerdem die Rolle **Global Administrator** oder
> **Privileged Role Administrator** in Entra ID sowie **Owner** oder
> **User Access Administrator** auf dem Storage Account.

---

## Übersicht

Die Veröffentlichen-Funktion lädt HTML- und Excel-Reports direkt in einen
privaten Azure Blob Storage Container hoch. Mitarbeiter rufen eine feste URL auf,
melden sich mit ihrem Firmenkonto (Azure AD) an und sehen eine Übersicht aller
veröffentlichten Reports – ohne Ablaufdatum, ohne separate Zugangsdaten.

```
CostCenter App  →  Azure Blob Storage (privat)  →  Browser + Azure AD Login
    Button              Service Principal               Firmenkonto
```

---

## Schritt 1 – Storage Account anlegen

Navigiere im **Azure Portal** zu:
**Speicherkonten → Erstellen**

| Feld | Wert |
|---|---|
| Ressourcengruppe | z.B. `rg-costcenter` *(oder bestehende nutzen)* |
| Speicherkontoname | Eindeutig, z.B. `costcenterreports` *(nur Kleinbuchstaben, Ziffern)* |
| Region | z.B. `Germany West Central` |
| Redundanz | `LRS` *(lokal redundant – ausreichend)* |

Alle anderen Einstellungen auf Standard lassen. Klicke auf **Erstellen**.

> 📋 Notiere dir den **Speicherkontonamen** – er wird später in der App eingetragen.

---

## Schritt 2 – Blob Container erstellen

Im neu erstellten Storage Account navigiere zu:
**Datenspeicher → Container → + Container**

| Feld | Wert |
|---|---|
| Name | `reports` |
| Öffentliche Zugriffsebene | **Privat (kein anonymer Zugriff)** |

Klicke auf **Erstellen**.

---

## Schritt 3 – Upload-Rechte für den Service Principal zuweisen

Damit die App Dateien hochladen darf, benötigt der Service Principal Schreibrechte
auf dem Container.

Navigiere im Storage Account zu:
**Zugriffssteuerung (IAM) → Rollenzuweisung hinzufügen**

| Feld | Wert |
|---|---|
| Rolle | `Storage-Blobdatenmitwirkender` *(Storage Blob Data Contributor)* |
| Zugriff zuweisen zu | Benutzer, Gruppe oder Dienstprinzipal |
| Mitglieder | `CostCenter-Reporter` *(App Registration aus SETUP_SERVICE_PRINCIPAL.md)* |

Klicke auf **Überprüfen und zuweisen**.

---

## Schritt 4 – Leserechte für Mitarbeiter zuweisen

Für jeden Mitarbeiter der die Reports öffnen soll, einmalig:

Navigiere im Storage Account zu:
**Zugriffssteuerung (IAM) → Rollenzuweisung hinzufügen**

| Feld | Wert |
|---|---|
| Rolle | `Storage-Blobdatenleser` *(Storage Blob Data Reader)* |
| Zugriff zuweisen zu | Benutzer, Gruppe oder Dienstprinzipal |
| Mitglieder | E-Mail-Adresse des Mitarbeiters auswählen |

Klicke auf **Überprüfen und zuweisen**.

> 💡 **Tipp:** Alternativ eine Azure AD Gruppe (z.B. `CostCenter-Viewer`) anlegen,
> die Gruppe einmalig als `Storage Blob Data Reader` zuweisen, und Mitarbeiter
> einfach zur Gruppe hinzufügen/entfernen – ohne erneute IAM-Änderungen.

---

## Schritt 5 – App Registration für den Browser-Login anlegen

Damit Mitarbeiter sich im Browser mit ihrem Firmenkonto anmelden können, wird
eine separate App Registration benötigt (nicht der Service Principal aus Schritt 3).

Navigiere im **Azure Portal** zu:
**Entra ID → App-Registrierungen → Neue Registrierung**

| Feld | Wert |
|---|---|
| Name | `CostCenter-Reports-Viewer` |
| Kontotyp | Nur Konten in diesem Organisationsverzeichnis |
| Umleitungs-URI – Plattform | **Single-Page-Anwendung (SPA)** |
| Umleitungs-URI – URL | `https://<account>.blob.core.windows.net/reports/index.html` |

Ersetze `<account>` mit dem Speicherkontonamen aus Schritt 1.

Klicke auf **Registrieren**.

> 📋 Notiere dir die **Anwendungs-ID (Client-ID)** dieser neuen App Registration.
> Sie wird in der App als **MSAL Client ID** eingetragen.

---

## Schritt 6 – API-Berechtigung für Storage hinzufügen

In der neuen App Registration navigiere zu:
**API-Berechtigungen → Berechtigung hinzufügen**

1. Klicke auf **Von meiner Organisation verwendete APIs**
2. Suche nach `Azure Storage` und wähle es aus
3. Wähle **Delegierte Berechtigungen**
4. Aktiviere `user_impersonation`
5. Klicke auf **Berechtigungen hinzufügen**

Danach:
**Administratorzustimmung für \<Tenant\> erteilen** → Klicke auf **Ja**

---

## Schritt 7 – Einstellungen in der App eintragen

Starte **CostCenter.exe** und scrolle zur Karte **☁ Publish to Azure**:

| Feld in der App | Wert |
|---|---|
| Storage Account Name | Speicherkontoname aus Schritt 1 *(z.B. `costcenterreports`)* |
| Container Name | `reports` |
| MSAL Client ID | Anwendungs-ID aus Schritt 5 *(für den Browser-Login)* |

> Tenant ID, Client ID und Client Secret werden automatisch aus der
> **Azure Authentication** Karte übernommen – nichts doppelt eintragen.

Klicke auf **💾 Save**.

---

## Ablauf nach dem Setup

1. Report wie gewohnt erstellen (**▶ Create Report**)
2. Wenn der Report fertig ist, wird der Button **☁ Veröffentlichen** aktiv
3. Klicke auf **☁ Veröffentlichen**
4. Die App lädt HTML + Excel hoch und aktualisiert die `index.html`
5. Ein Popup zeigt die fertige URL – auf **Ja** klicken öffnet den Browser direkt:
   ```
   https://costcenterreports.blob.core.windows.net/reports/index.html
   ```
6. Mitarbeiter rufen diese URL auf → melden sich mit Firmenkonto an → sehen alle Reports

Die URL bleibt bei jeder Veröffentlichung identisch – du musst keinen neuen
Link verschicken. Neue Reports erscheinen automatisch in der Übersicht.

---

## Mitarbeiter hinzufügen oder entfernen

**Hinzufügen:** Schritt 4 wiederholen mit der E-Mail-Adresse des neuen Mitarbeiters.

**Entfernen:** Im Storage Account unter **Zugriffssteuerung (IAM) → Rollenzuweisungen**
die entsprechende Zeile suchen und löschen. Der Zugriff ist sofort entzogen.

---

## Kosten

| Posten | Schätzung |
|---|---|
| Speicher (< 10 MB Reports) | < 0,01 €/Monat |
| Ausgehender Datenverkehr | < 0,01 €/Monat |
| Transaktionen | < 0,01 €/Monat |
| **Gesamt** | **< 0,05 €/Monat** |

---

> 🔒 **Sicherheitshinweis:** Der Container ist privat – kein anonymer Zugriff möglich.
> Nur Benutzer mit explizit zugewiesener IAM-Rolle können die Inhalte lesen.
> Der Service Principal hat ausschließlich Schreibrechte auf den Container,
> keine Verwaltungsrechte auf den Storage Account.
