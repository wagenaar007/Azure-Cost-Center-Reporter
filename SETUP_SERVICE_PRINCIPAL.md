# Service Principal einrichten
### Azure CostCenter Reporter – Einrichtungsanleitung

> **Voraussetzung:** Du benötigst die Rolle **Global Administrator** oder  
> **Privileged Role Administrator** in Entra ID sowie **Owner** oder  
> **User Access Administrator** auf den jeweiligen Subscriptions.

---

## Schritt 1 – App Registration anlegen

Navigiere im **Azure Portal** zu:  
**Entra ID → App-Registrierungen → Neue Registrierung**

| Feld | Wert |
|---|---|
| Name | `CostCenter-Reporter` |
| Kontotyp | Nur Konten in diesem Organisationsverzeichnis |
| Umleitungs-URI | *(leer lassen)* |

Klicke auf **Registrieren**.

> 📋 Notiere dir auf der Übersichtsseite der neuen App Registration:
> - **Anwendungs-ID (Client-ID)**
> - **Verzeichnis-ID (Tenant-ID)**
>
> Beide Werte werden später in der CostCenter-App eingetragen.

---

## Schritt 2 – Client Secret erstellen

Öffne die App Registration und navigiere zu:  
**Zertifikate & Geheimnisse → Geheime Clientschlüssel → Neuer geheimer Clientschlüssel**

| Feld | Wert |
|---|---|
| Beschreibung | `CostCenter-Secret` |
| Ablauf | 1 Jahr *(oder nach Bedarf)* |

Klicke auf **Hinzufügen**.

> ⚠️ **Wichtig:** Das Secret wird **nur einmal** angezeigt!  
> Kopiere den Wert in der Spalte **Wert** sofort – nicht die Spalte „Geheimnis-ID" (GUID).

---

## Schritt 3 – Cost Management Reader zuweisen

Dieser Schritt muss für **jede Subscription** einzeln durchgeführt werden.

Navigiere zu:  
**Abonnements → \<Subscription auswählen\> → Zugriffssteuerung (IAM) → Rollenzuweisung hinzufügen**

| Feld | Wert |
|---|---|
| Rolle | `Cost Management-Leseberechtigter` |
| Zugriff zuweisen zu | Benutzer, Gruppe oder Dienstprinzipal |
| Mitglieder | `CostCenter-Reporter` *(App Registration suchen)* |

Klicke auf **Überprüfen und zuweisen**.

Wiederhole diesen Schritt für alle Subscriptions, die überwacht werden sollen.

---

## Abschluss – Daten in die App eintragen

Starte **CostCenter.exe** und trage folgende Werte ein:

| Feld in der App | Quelle |
|---|---|
| Tenant-ID | Verzeichnis-ID aus Schritt 1 |
| Client-ID | Anwendungs-ID aus Schritt 1 |
| Client Secret | Wert aus Schritt 2 |
| Subscription-IDs | IDs der Subscriptions aus Schritt 3 |

---

> 🔒 **Sicherheitshinweis:** Der Service Principal besitzt ausschließlich Leserechte  
> auf die Kostendaten. Es werden keine Schreib- oder Verwaltungsrechte benötigt.

---

## Secret erneuern (nach Ablauf)

Navigiere zur App Registration:  
**Zertifikate & Geheimnisse → Geheime Clientschlüssel → Neuer geheimer Clientschlüssel**

Neues Secret erstellen, Wert kopieren und in der CostCenter-App unter **Client Secret** aktualisieren.

