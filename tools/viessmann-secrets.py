#!/usr/bin/env python3
"""ViCare-Zugangsdaten aus der jsondb heraushalten bzw. wieder einsetzen.

Das Repository ist öffentlich. Die Viessmann-Things speichern Client-ID, ViCare-Login,
Passwort, Installations-ID und Gateway-Seriennummer im Klartext in
org.openhab.core.thing.Thing.json. Dieses Skript

  strip  <jsondb-ordner>                   leert diese Werte (vor jedem Commit)
  inject <jsondb-ordner> <secrets.json>    setzt sie aus einer lokalen Datei ein (vor dem Kopieren in den Container)
  check  <jsondb-ordner>                   Exit-Code 1, wenn noch Werte drinstehen (z. B. als pre-commit-Hook)

Die Datei secrets.json (Vorlage: viessmann-secrets.example.json) liegt nur lokal und steht in .gitignore.
"""
import json
import os
import sys

THINGS = "org.openhab.core.thing.Thing.json"
ACCOUNT_KEYS = ("apiKey", "user", "password")
GATEWAY_KEYS = ("installationId", "gatewaySerial")


def dumps(data):
    """Schreibt JSON so wie openHAB (Gson): 2 Leerzeichen, Umlaute roh, = < > & ' escaped."""
    s = json.dumps(data, indent=2, ensure_ascii=False, separators=(",", ": "))
    for c, r in (("=", "\\u003d"), ("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026"), ("'", "\\u0027")):
        s = s.replace(c, r)
    return s


def targets(things):
    """Liefert (Thing-Wert, Abschnitt, Schlüssel) für alle zu schützenden Felder."""
    for entry in things.values():
        thing = entry["value"]
        ttype = thing.get("thingTypeUID", "")
        if ttype in ("viessmann:account", "viessmann:bridge"):
            for k in ACCOUNT_KEYS:
                yield thing, "configuration", k
        if ttype in ("viessmann:gateway", "viessmann:bridge"):
            for k in GATEWAY_KEYS:
                yield thing, "configuration", k
        if ttype.startswith("viessmann:"):
            # Das Binding schreibt Installations-ID und Seriennummer zusätzlich in die Thing-Eigenschaften.
            for k in GATEWAY_KEYS:
                yield thing, "properties", k


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("strip", "inject", "check"):
        sys.exit(__doc__)
    cmd, folder = sys.argv[1], sys.argv[2]
    path = os.path.join(folder, THINGS)
    with open(path, encoding="utf-8") as f:
        things = json.load(f)

    secrets = {}
    if cmd == "inject":
        if len(sys.argv) < 4 or not os.path.isfile(sys.argv[3]):
            sys.exit("Fehler: secrets-Datei fehlt. Vorlage viessmann-secrets.example.json kopieren und ausfüllen.")
        with open(sys.argv[3], encoding="utf-8") as f:
            secrets = json.load(f)
        missing = [k for k in ACCOUNT_KEYS if not str(secrets.get(k, "")).strip()]
        if missing:
            sys.exit("Fehler: in der secrets-Datei fehlen Werte für: " + ", ".join(missing))
        if not all(str(secrets.get(k, "")).strip() for k in GATEWAY_KEYS):
            # Beim ersten Start sind die beiden Werte noch unbekannt: Der Account findet das Gateway
            # dann in der Inbox, dort stehen Installations-ID und Seriennummer.
            print("Hinweis: installationId/gatewaySerial fehlen noch, das Gateway-Thing bleibt bis dahin offline.")
            for k in GATEWAY_KEYS:
                secrets[k] = str(secrets.get(k, "")).strip()

    found = []
    for thing, section, key in targets(things):
        values = thing.setdefault(section, {})
        if cmd == "check":
            if values.get(key):
                found.append(f"{thing['UID']} {section}.{key}")
        elif cmd == "strip":
            if section == "properties":
                values.pop(key, None)
            elif key in values or section == "configuration":
                values[key] = ""
        else:  # inject
            if section == "configuration":
                values[key] = secrets[key]
            # properties setzt das Binding beim Start selbst

    if cmd == "check":
        if found:
            print("Zugangsdaten in der jsondb gefunden (vorher 'strip' ausführen):", *found, sep="\n  ")
            sys.exit(1)
        return

    with open(path, "w", encoding="utf-8") as f:
        f.write(dumps(things))
    print(f"{cmd}: {path}")


if __name__ == "__main__":
    main()
