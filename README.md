# openhab-s6

openHAB-Konfiguration (openHAB 5.2.4 im Docker-Container) zur Überwachung von
Stromzähler, PV-Anlage mit Hybrid-Wechselrichter und Batteriespeicher sowie
von drei Wärmemengenzählern.

Die gesamte Konfiguration ist über die openHAB-Oberfläche (Main UI) angelegt
und liegt deshalb in `userdata/jsondb/` (Things, Items, Links, Metadaten,
Regeln, Seiten). Textdateien unter `conf/` werden nicht verwendet.

---

## Abgefragte Geräte

| Gerät | Anbindung | Adresse | Zweck |
|---|---|---|---|
| Hauptstromzähler | HTTP (JSON) | `http://pi-8g:8080/energy`, alle 5 s | Netzbezug, Zählerstände Bezug/Einspeisung |
| GoodWe GW10K-ET (Hybrid-Wechselrichter) | Modbus TCP | `192.168.178.67:502`, Slave-ID 1 | PV-Leistung, Hausverbrauch, Akkudaten, Netzladen |
| Pylontech Force H1, 6 Module (20,24 kWh nutzbar) | über den GoodWe (BMS-Register) | – | Akkustand, SOH, Entladung |
| Kamstrup MULTICAL 603 „Haus_Heizkörper“ | Modbus TCP (Modul E1 Modbus/KMP TCP/IP) | `192.168.178.101:502`, Slave-ID 1 | Wärmemenge |
| Kamstrup MULTICAL 603 „EG_DG_Fußbodenheizung“ | Modbus TCP (Modul E1 Modbus/KMP TCP/IP) | `192.168.178.100:502`, Slave-ID 1 | Wärmemenge |
| Kamstrup MULTICAL 603 „Keller_Fussbodenheizung“ | Modbus TCP (Modul E1 Modbus/KMP TCP/IP) | `192.168.178.102:502`, Slave-ID 1 | Wärmemenge |

### Hauptstromzähler (HTTP)

Thing `http:url:69363a4913` liest JSON von `http://pi-8g:8080/energy`:

| JSON-Feld | Item | Einheit |
|---|---|---|
| `$.power` | `HauptstromzaehlerPower` | W |
| `$.v_1_8_0` | `HauptstromzaehlerVerbrauch` | kWh (OBIS 1.8.0) |
| `$.v_2_8_0` | `HauptstromzaehlerEinspeisung` | kWh (OBIS 2.8.0) |

### GoodWe GW10K-ET (Modbus TCP)

Bridge `modbus:tcp:Goodwe`. Alle Register sind Holding-Register mit 0-basierter Adresse.

| Poller | Register | Typ | Item | Bedeutung |
|---|---|---|---|---|
| 35100 (Länge 120, 5 s) | 35105 | uint32 | `Goodwe_PV1_Power` | PV-Strang 1 (MPPT1), W |
| | 35109 | uint32 | `Goodwe_PV2_Power` | PV-Strang 2 (MPPT2), W |
| | 35138 | int16 | `Goodwe_Live_Data_Value_as_Number` | PV & Stromspeicher, W |
| | 35172 | int16 | `Hausverbrauch` | Gesamte Lastleistung (Load), W |
| | 35209 | uint32 | `Goodwe_Batt_Entladung_Raw` | Akku-Entladung gesamt seit Installation, 0,1 kWh |
| 37000 (Länge 10, 5 s) | 37007 | uint16 | `Akkustand` | Ladezustand (SOC), % |
| | 37008 | uint16 | `Akku_SOH` | Gesundheitszustand (SOH), % |
| 47511 (Länge 2, 2 s) | 47511 | uint16 lesen / int16 schreiben | `Goodwe_EMS_Mode` | EMS-Modus: 1 = Automatik, 2 = Laden |
| | 47512 | uint16 lesen / int16 schreiben | `Goodwe_EMS_Power` | EMS-Lade-/Entladeleistung, W |

### Kamstrup MULTICAL 603 (Modbus TCP)

Je Zähler eine eigene Bridge. Der Poller liest Adresse 20 mit Länge 2 alle 30 s,
das Data-Thing interpretiert den Wert als `float32` (Big-Endian). Der Wert ist die Wärmemenge in MWh.

Entspricht dem Testbefehl:

```bash
mbpoll -m tcp -a 1 -t 4:float -B -r 21 -c 1 -p 502 <IP>
```

`mbpoll -r` zählt ohne `-0` ab 1, openHAB zählt ab 0. Deshalb steht in openHAB Adresse 20.

---

## Seiten

### Overview

| Kachel | Item | Anzeige | Quelle |
|---|---|---|---|
| Netzbezug | `HauptstromzaehlerPower` | W | Hauptzähler |
| Hauptstromzähler Einspeisung | `HauptstromzaehlerEinspeisung` | kWh | Hauptzähler |
| Hauptstromzähler Verbrauch | `HauptstromzaehlerVerbrauch` | kWh | Hauptzähler |
| PV&Stromspeicher | `Goodwe_Live_Data_Value_as_Number` | W | GoodWe 35138 |
| Hausverbrauch | `Hausverbrauch` | W | GoodWe 35172 |
| Akkustand | `Akkustand` | % | GoodWe 37007 |
| Akku Gesundheit (SOH) | `Akku_SOH` | % | GoodWe 37008 |
| Akku Ladezyklen | `Akku_Ladezyklen` | Zyklen, Untertitel: Gesamtentladung in kWh | berechnet aus GoodWe 35209 |
| PV Strang 1 | `Goodwe_PV1_Power` | W | GoodWe 35105 |
| PV Strang 2 | `Goodwe_PV2_Power` | W | GoodWe 35109 |
| PV Gesamtleistung | `Goodwe_PV_Total_Power` | W | Summe PV1 + PV2 (Gruppe mit SUM) |
| Akku aus Netz laden | `Goodwe_Netzladen` | Schalter | GoodWe 47511/47512 |

Ein Klick auf eine Wert-Kachel öffnet den Verlauf (Analyzer).

### Wärmezähler

Eigene Seite in der Seitenleiste:

| Kachel | Item | Anzeige | Gerät |
|---|---|---|---|
| Haus_Heizkörper | `Waerme_Haus_Heizkoerper` | MWh | MULTICAL 603, 192.168.178.101 |
| EG_DG_Fußbodenheizung | `Waerme_EG_DG_Fussbodenheizung` | MWh | MULTICAL 603, 192.168.178.100 |
| Keller_Fussbodenheizung | `Waerme_Keller_Fussbodenheizung` | MWh | MULTICAL 603, 192.168.178.102 |

---

## Regeln

| Regel | Auslöser | Funktion |
|---|---|---|
| Netzladen schalten | Befehl an `Goodwe_Netzladen` | EIN: 47512 = 3000 W, dann 47511 = 2. AUS: 47511 = 1, dann 47512 = 0. |
| Netzladen Status | Update von `Goodwe_EMS_Mode` | Setzt den Schalter auf den tatsächlich gelesenen Zustand: 47511 = 2 heißt AN, alles andere AUS. |
| Akku Ladezyklen berechnen | Änderung von `Goodwe_Batt_Entladung_Raw` | Gesamtentladung in kWh = Rohwert ÷ 10. Ladezyklen = Gesamtentladung ÷ 20,24 kWh. |

Hinweise:

- `Goodwe_Netzladen`, `Goodwe_EMS_Mode` und `Goodwe_EMS_Power` haben `autoupdate=false`.
  Der Schalter zeigt also immer den Zustand, den der Wechselrichter zurückmeldet. Nach einem Klick springt
  er erst um, wenn der Wechselrichter den neuen Modus bestätigt hat, also nach höchstens etwa 2 s.
- Die Ladezyklen sind ein Rechenwert aus dem Entladezähler des Wechselrichters und kein Wert aus dem BMS.
  Die nutzbare Kapazität (20,24 kWh) steht in der Regel und muss bei einer Erweiterung des Akkus angepasst werden.

---

## Verwendete openHAB-Add-ons

| Add-on | Typ | Wofür |
|---|---|---|
| HTTP Binding (`binding-http`) | Binding | Hauptstromzähler über JSON-Endpunkt |
| Modbus Binding (`binding-modbus`) | Binding | GoodWe-Wechselrichter und MULTICAL-603-Zähler |
| JSONPath Transformation (`transformation-jsonpath`) | Transformation | Werte aus der JSON-Antwort des Hauptzählers lesen |
| RRD4j Persistence (`persistence-rrd4j`) | Persistence | Verlauf aller Items (`*`), Strategie everyChange + everyMinute + restoreOnStartup |

Regeln sind als UI-Regeln mit Rules DSL angelegt. Dafür ist kein zusätzliches Add-on nötig.

---

## Repository-Struktur

```
userdata/jsondb/
├── automation_rules.json                                   Regeln
├── org.openhab.core.items.Item.json                        Items
├── org.openhab.core.items.Metadata.json                    Anzeigeformate, autoupdate
├── org.openhab.core.persistence.PersistenceServiceConfiguration.json   RRD4j-Konfiguration
├── org.openhab.core.thing.Thing.json                       Things und Bridges
├── org.openhab.core.thing.link.ItemChannelLink.json        Item-Channel-Links
└── uicomponents_ui_page.json                               Seiten (Overview, Wärmezähler)
```

Nicht im Repository (siehe `.gitignore`): `users.json` mit Zugangsdaten, `jsondb/backup/`, Logs, Cache und Persistence-Daten.

---

## Betrieb

### Änderungen aus dem Repo in den Container übernehmen

openHAB muss dabei **gestoppt** sein. Sonst überschreibt openHAB die Dateien beim Beenden mit seinem alten Stand.

```bash
cd ~/openhab
CID=$(docker-compose ps -q openhab)
docker-compose stop
docker cp ~/git/openhab-s6/userdata/jsondb/. $CID:/openhab/userdata/jsondb/
docker-compose start
```

### Im UI gemachte Änderungen ins Repo holen

```bash
cd ~/openhab
CID=$(docker-compose ps -q openhab)
docker cp $CID:/openhab/userdata/jsondb/. ~/git/openhab-s6/userdata/jsondb/
cd ~/git/openhab-s6 && git status
```

### openHAB-Update

Nach einem Versionswechsel den Karaf-Cache leeren. Sonst laden die Bindings unter Umständen nicht,
und die Things melden `HANDLER_MISSING_ERROR`.

```bash
cd ~/openhab
docker-compose stop
docker-compose pull
docker-compose run --rm --entrypoint sh openhab -c 'rm -rf /openhab/userdata/cache/* /openhab/userdata/tmp/*'
docker-compose up -d
```
