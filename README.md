# openhab-s6

openHAB-Konfiguration (openHAB 5.2.4 im Docker-Container) zur Überwachung von
Stromzähler, PV-Anlage mit Hybrid-Wechselrichter und Batteriespeicher,
drei Wärmemengenzählern sowie der Wärmepumpe Viessmann Vitocal 250-A.

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
| Viessmann Vitocal 250-A (Luft/Wasser-Wärmepumpe) | Viessmann-Cloud-API über das eingebaute WLAN-Modul | `api.viessmann-climatesolutions.com`, Abfrage automatisch (ca. alle 1–2 min) | Temperaturen, Betrieb, Energie, Sollwerte |

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

### Viessmann Vitocal 250-A (Viessmann-API)

Einen lokalen Zugriff über die IP-Adresse bietet Viessmann nicht. Das WLAN-Modul spricht nur mit der Cloud.
Die Anbindung läuft deshalb über das openHAB-Viessmann-Binding und die Viessmann-API.

| Thing | UID | Inhalt |
|---|---|---|
| Account (Bridge) | `viessmann:account:vicare` | Client-ID, ViCare-Login, Grenze 1450 Aufrufe/Tag, Abfrageintervall automatisch |
| Gateway (Bridge) | `viessmann:gateway:vicare:gateway` | Installations-ID und Seriennummer des WLAN-Moduls, Störungsmeldungen |
| Gerät | `viessmann:device:vicare:gateway:vitocal` | `deviceId` 0 = die Wärmepumpe. Die Kanäle legt das Binding selbst aus den gemeldeten Features an. |

Die UIDs sind fest vergeben, damit die Links im Repo passen. Die Inbox schlägt Gateway und Gerät zusätzlich
unter anderen UIDs vor (mit der Seriennummer im Namen). Diese Vorschläge ignorieren, nicht hinzufügen.

Die Kanal-ID entsteht aus dem Feature-Namen der API: Punkte werden zu Bindestrichen, aus camelCase wird
kebab-case, nach `#` folgt die Eigenschaft. Beispiel: `heating.dhw.sensors.temperature.hotWaterStorage` / `value`
→ `heating-dhw-sensors-temperature-hot-water-storage#value`.

| Item | Feature (Eigenschaft) | Einheit | schreibbar |
|---|---|---|---|
| `WP_Aussentemperatur` | `heating.sensors.temperature.outside` | °C | |
| `WP_Vorlauftemperatur` | `heating.circuits.0.sensors.temperature.supply` | °C | |
| `WP_Vorlauf_Soll` | `heating.circuits.0.temperature` | °C | |
| `WP_Ruecklauftemperatur` | `heating.sensors.temperature.return` | °C | |
| `WP_Warmwasser_Ist` | `heating.dhw.sensors.temperature.hotWaterStorage` | °C | |
| `WP_Warmwasser_Soll` | `heating.dhw.temperature.main` | °C | ja, 10–60 °C |
| `WP_Raum_Soll_Normal` | `heating.circuits.0.operating.programs.normalHeating` (`temperature`) | °C | ja, 3–37 °C |
| `WP_Betriebsart` | `heating.circuits.0.operating.modes.active` | `heating` / `standby` | ja |
| `WP_Programm` | `heating.circuits.0.operating.programs.active` | Text | |
| `WP_Warmwasser_Modus` | `heating.dhw.operating.modes.active` | `efficient` / `efficientWithMinComfort` / `off` | ja |
| `WP_Warmwasser_Einmalladung` | `heating.dhw.oneTimeCharge` (`active`) | Schalter | ja |
| `WP_Verdichter_Aktiv` | `heating.compressors.0` (`active`) | Schalter | |
| `WP_Verdichter_Phase` | `heating.compressors.0` (`phase`) | Text | |
| `WP_Verdichter_Drehzahl` | `heating.compressors.0.speed.current` | Hz (= U/s) | |
| `WP_Verdichter_Starts` | `heating.compressors.0.statistics` (`starts`) | Anzahl | |
| `WP_Verdichter_Stunden` | `heating.compressors.0.statistics` (`hours`) | h | |
| `WP_Leistung_Elektrisch` | `heating.inverters.0.sensors.power.output` | W | |
| `WP_Abtauung` | `heating.outdoor.defrosting` (`active`) | Schalter | |
| `WP_Anlagendruck` | `heating.sensors.pressure.supply` | bar | |
| `WP_Strom_Heizen_Heute` / `_Jahr` | `heating.power.consumption.summary.heating` (`currentDay` / `currentYear`) | kWh | |
| `WP_Strom_Warmwasser_Heute` / `_Jahr` | `heating.power.consumption.summary.dhw` (`currentDay` / `currentYear`) | kWh | |
| `WP_Waerme_Heizen_Heute` / `_Jahr` | `heating.heat.production.summary.heating` (`currentDay` / `currentYear`) | kWh | |
| `WP_Waerme_Warmwasser_Heute` / `_Jahr` | `heating.heat.production.summary.dhw` (`currentDay` / `currentYear`) | kWh | |
| `WP_JAZ` | `heating.scop.total` | – | |
| `WP_Strom_Heute`, `WP_Waerme_Heute` | Gruppen mit SUM aus Heizen + Warmwasser | kWh | |
| `WP_COP_Heute` | berechnet (Regel) | – | |
| `WP_Fehler_Aktiv`, `WP_Letzte_Fehlermeldung` | Gateway-Kanäle `error-is-active`, `last-error-message` | | |
| `WP_API_Aufrufe_Heute` | Account-Kanal `count-api-calls` | Anzahl | |

Hinweise:

- Die API liefert nur, was die Anlage meldet. Fehlt bei deiner Anlage ein Feature (z. B. ohne Warmwasserspeicher),
  bleibt das Item `NULL`. Alle tatsächlich vorhandenen Kanäle zeigt das Gerät-Thing im Tab „Channels“.
- Werte mit der Einheit `liter/hour` (Volumenstrom) kennt das Binding nicht und legt dafür keinen Kanal an.
- Nach einem Befehl (Sollwert, Betriebsart) zeigt die Oberfläche den neuen Wert sofort an. Den von der
  Wärmepumpe bestätigten Wert gibt es erst mit der nächsten Abfrage.
- Grenze im kostenlosen API-Paket: 120 Aufrufe in 10 Minuten und 1450 in 24 Stunden, sonst 24 Stunden Sperre.
  Die ViCare-App zählt mit, wenn sie dasselbe Konto nutzt. Das Binding plant 450 Aufrufe als Puffer für Befehle und
  die App ein (`bufferApiCommands`). Den Verbrauch zeigt `WP_API_Aufrufe_Heute`.

#### Einrichtung

1. Im [Viessmann Developer Portal](https://developer.viessmann.com/) mit dem ViCare-Konto
   anmelden und einen Client anlegen: Name `openhab`, Google reCAPTCHA **aus**, Redirect-URI
   `http://localhost:8080/viessmann/authcode/`. Die Client-ID kopieren.
2. `viessmann-secrets.example.json` nach `viessmann-secrets.json` kopieren und `apiKey` (Client-ID), `user` und
   `password` (ViCare-Login) eintragen. Die Datei steht in `.gitignore` und darf nicht ins Repo.
3. Die Konfiguration wie unter „Betrieb“ beschrieben in den Container übernehmen. Der Account geht online,
   das Gateway bleibt noch offline.
4. In der Inbox erscheint „Viessmann Gateway“. Dort `installationId` und `gatewaySerial` ablesen (Eigenschaften
   des Vorschlags), in `viessmann-secrets.json` eintragen und die Konfiguration noch einmal übernehmen. Den
   Inbox-Vorschlag danach ignorieren.

#### Zugangsdaten und öffentliches Repo

Das Repository ist öffentlich. openHAB speichert die Werte aus `viessmann-secrets.json` im Klartext in
`org.openhab.core.thing.Thing.json`. `tools/viessmann-secrets.py` hält sie heraus:

| Befehl | Wann | Wirkung |
|---|---|---|
| `strip <jsondb>` | nach dem Holen aus dem Container, vor jedem Commit | leert Client-ID, Login, Passwort, Installations-ID und Seriennummer |
| `inject <jsondb> viessmann-secrets.json` | vor dem Kopieren in den Container (auf einer Kopie) | setzt die Werte ein |
| `check <jsondb>` | optional als pre-commit-Hook | bricht ab, wenn noch Werte drinstehen |

Pre-commit-Hook einrichten (einmalig):

```bash
cd ~/git/openhab-s6
printf '#!/bin/sh\nexec python3 tools/viessmann-secrets.py check userdata/jsondb\n' > .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

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

### Wärmepumpe

Eigene Seite in der Seitenleiste mit vier Blöcken:

| Block | Kacheln |
|---|---|
| Temperaturen | Außentemperatur, Vorlauf (Untertitel: Soll), Rücklauf, Warmwasser (Untertitel: Soll) |
| Betrieb | Betriebsart Heizkreis und Warmwasser-Betriebsart (Klick öffnet Auswahl), Warmwasser-Einmalladung (Schalter), elektrische Leistung (Untertitel: Verdichter an/aus, Drehzahl), Verdichter-Starts (Untertitel: Laufzeit), Anlagendruck, Störung (Untertitel: letzte Meldung), API-Aufrufe heute |
| Energie | Strom heute, Wärme heute (jeweils Heizen/WW im Untertitel), Arbeitszahl heute, Jahresarbeitszahl, Strom und Wärme Heizen dieses Jahr (Untertitel: Warmwasser) |
| Sollwerte | Stepper für Warmwasser Soll und Raumtemperatur Soll (Normal) |

---

## Regeln

| Regel | Auslöser | Funktion |
|---|---|---|
| Netzladen schalten | Befehl an `Goodwe_Netzladen` | EIN: 47512 = 3000 W, dann 47511 = 2. AUS: 47511 = 1, dann 47512 = 0. |
| Netzladen Status | Update von `Goodwe_EMS_Mode` | Setzt den Schalter auf den tatsächlich gelesenen Zustand: 47511 = 2 heißt AN, alles andere AUS. |
| Akku Ladezyklen berechnen | Änderung von `Goodwe_Batt_Entladung_Raw` | Gesamtentladung in kWh = Rohwert ÷ 10. Ladezyklen = Gesamtentladung ÷ 20,24 kWh. |
| Wärmepumpe Arbeitszahl heute berechnen | Änderung eines der vier Tageszähler `WP_Strom_*_Heute` / `WP_Waerme_*_Heute` | `WP_COP_Heute` = Wärme heute ÷ Strom heute (Heizen + Warmwasser). Unter 0,1 kWh Strom bleibt der Wert leer. |

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
| Viessmann Binding (`binding-viessmann`) | Binding | Wärmepumpe Vitocal 250-A über die Viessmann-API |
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
└── uicomponents_ui_page.json                               Seiten (Overview, Wärmezähler, Wärmepumpe)
tools/
└── viessmann-secrets.py                                    ViCare-Zugangsdaten entfernen/einsetzen
viessmann-secrets.example.json                              Vorlage für viessmann-secrets.json
```

Nicht im Repository (siehe `.gitignore`): `users.json` mit Zugangsdaten, `viessmann-secrets.json`, `jsondb/backup/`, Logs, Cache und Persistence-Daten.

---

## Betrieb

### Änderungen aus dem Repo in den Container übernehmen

openHAB muss dabei **gestoppt** sein. Sonst überschreibt openHAB die Dateien beim Beenden mit seinem alten Stand.

Die ViCare-Zugangsdaten werden dabei auf einer temporären Kopie eingesetzt. Ohne `viessmann-secrets.json`
bricht der Ablauf vor dem Kopieren ab, damit die Zugangsdaten im Container nicht überschrieben werden.

```bash
cd ~/openhab
CID=$(docker-compose ps -q openhab)
TMP=$(mktemp -d)
cp -r ~/git/openhab-s6/userdata/jsondb/. $TMP/ \
  && python3 ~/git/openhab-s6/tools/viessmann-secrets.py inject $TMP ~/git/openhab-s6/viessmann-secrets.json \
  && docker-compose stop \
  && docker cp $TMP/. $CID:/openhab/userdata/jsondb/ \
  && docker-compose start
rm -rf $TMP
```

### Im UI gemachte Änderungen ins Repo holen

Danach immer `strip` ausführen, sonst landen die ViCare-Zugangsdaten im öffentlichen Repo.

```bash
cd ~/openhab
CID=$(docker-compose ps -q openhab)
docker cp $CID:/openhab/userdata/jsondb/. ~/git/openhab-s6/userdata/jsondb/
python3 ~/git/openhab-s6/tools/viessmann-secrets.py strip ~/git/openhab-s6/userdata/jsondb
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
