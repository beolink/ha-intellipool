# Home Assistant – Pentair Intellipool integration

Custom integration för **Pentair Intellipool INTP-1010B** (och kompatibla modeller).

Stöder:
- **Lokal anslutning** direkt mot controllerns IP på hemmanätverket *(rekommenderat)*
- **Molnanslutning** via [intellipool.eu](https://www.intellipool.eu) som fallback

---

## Entiteter

| Plattform | Entitet | Beskrivning |
|---|---|---|
| `sensor` | Vattentemperatur | °C |
| `sensor` | Lufttemperatur | °C |
| `sensor` | pH | pH-värde |
| `sensor` | ORP / Redox | mV |
| `sensor` | Salthalt (konduktivitet) | g/L |
| `sensor` | Filtreringshastighet | rpm |
| `sensor` | Pumpflöde | m³/h |
| `sensor` | Pumpeffekt | W |
| `sensor` | Sensorbatteri (diagnostik) | V |
| `sensor` | Radiosignal (diagnostik) | dB |
| `sensor` | Statusmeddelande (diagnostik) | text |
| `sensor` | Datakälla (diagnostik) | primary/fallback |
| `switch` | Pump | På/av |
| `switch` | Filtrering | På/av |
| `switch` | Uppvärmning | På/av |
| `switch` | Belysning | På/av |
| `switch` | Elektrolys/Klorering | På/av |
| `switch` | pH-dosering | På/av |
| `switch` | ORP-dosering | På/av |
| `switch` | Extra 1–3 (AUX) | Auxiliära utgångar |
| `climate` | Poolvärmning | HVAC-entitet med temperaturmål |
| `number` | pH-börvärde | 6.8–7.8 |
| `number` | ORP-börvärde | 200–800 mV |

---

## Installation

### Via HACS (rekommenderat)
1. Lägg till detta repo som custom repository i HACS
2. Sök efter "Intellipool" och installera
3. Starta om Home Assistant

### Manuell installation
```bash
cp -r custom_components/intellipool /config/custom_components/
```
Starta om Home Assistant, gå sedan till **Inställningar → Enheter & tjänster → Lägg till integration → Intellipool**.

---

## Konfiguration

### ⚠️ Viktigt om INTP-1010B och lokal anslutning

**INTP-1010B kör ingen lokal server.** Detta är verifierat empiriskt (juli 2026) mot
en riktig enhet på `10.0.11.44`:

| Test | Resultat |
|---|---|
| ARP (lager 2) | ✅ Enheten svarar — MAC `00:0B:3C` (Cygnal / Silicon Labs, egen inbäddad modul) |
| ICMP ping | ❌ Blockeras |
| **Alla 65535 TCP-portar** | ❌ **Inga öppna** — alla anslutningar tyst-droppas |
| UDP mDNS / SSDP / beacons | ❌ Enheten annonserar/sänder ingenting |

Enheten gör **enbart utgående** anslutningar till `intellipool.eu`. Det finns alltså
ingen lokal IP-port att ansluta till — direkt lokal integration är **inte möjlig** på
den här hårdvaran. (Samma gäller europeiska Hayward/Bayrol — alla är molnbaserade.)

Den lokala anslutningstypen i pluginen finns kvar för andra/framtida modeller (t.ex.
enheter med öppen webbserver) och för avancerad proxy-uppsättning (se längst ned).

**➡️ För INTP-1010B: använd molnanslutning.**

### Tre anslutningssätt

| Typ | Källa | Värden | Not |
|---|---|---|---|
| **Moln** *(rek.)* | intellipool.eu (skrapning) | Flest (alla sensorer + börvärden) | Login + serienummer |
| **Officiellt API** | api.domotique-piscine.eu | Färre (temp, pH, ORP, salt, flaggor) | Nyckelbaserat, stabilt |
| **Lokalt** | Enhetens IP | — | Ej INTP-1010B (ingen lokal server) |

### Molnanslutning (rekommenderat för INTP-1010B)

1. Välj **Molnanslutning** i config-flödet
2. Ange din e-postadress och lösenord för intellipool.eu
3. Pool-serienummer identifieras automatiskt (eller ange manuellt)
4. *(Valfritt)* Ange **installations-ID + API-nyckel** för att aktivera failsafe (se nedan)

> **Status:** Login **och sensordata fungerar** (verifierat mot riktig INTP-1010B).
> Kvar att fånga är endast **styr-kommandona** (pump/värme/ljus) — se nedan.

### Officiellt API (domotique-piscine.eu)

Ett rent, nyckelbaserat REST-API (tjänsten bakom intellipool.eu). Färre värden än
skrapningen men mycket stabilt. Ditt REST-URL avslöjar båda uppgifterna:

```
https://api.domotique-piscine.eu/api/install/<INSTALL-ID>/probe/water-temp?key=<API-NYCKEL>
```

- Välj **Officiellt API** i config-flödet och ange installations-ID + API-nyckel
- Integrationen använder bulk-endpointen `/api/install/<id>/probes?key=<nyckel>`
  (ett anrop → alla värden)

Stödda värden: vattentemperatur, lufttemperatur, pH, ORP, konduktivitet (salt),
samt flaggor för filtrering, uppvärmning, belysning och AUX.

### Failsafe (moln + officiellt API)

Du kan köra molnskrapningen som primär källa **med det officiella API:et som reserv**.
Ange install-ID + API-nyckel i molnsteget. Då gäller:

- Normalt används molnskrapningen (flest värden)
- Om skrapningen **slutar svara** eller dess tidsstämpel **slutar uppdateras** i
  mer än X minuter (standard 30, ställbart i inställningarna), växlar integrationen
  automatiskt till det officiella API:et
- Värden som bara skrapningen har (pumphastighet, effekt, börvärden, batteri) behålls
  från senaste lyckade hämtning så entiteterna inte blir otillgängliga
- Diagnostiksensorn **Datakälla** visar `primary` eller `fallback` så du ser när
  reserven är aktiv

### Vad som är bekräftat och inbyggt

`intellipool.eu` är en äldre **PHP-app bakom nginx** (jQuery 1.7.2 + w2ui), `PHPSESSID`-session.

| Del | Status | Detalj |
|---|---|---|
| Login | ✅ Bekräftat | `POST /pool/poolLogin/login`, fält `login` + `pass` (klartext/TLS) |
| Serienummer | ✅ Auto | Extraheras från `displaySummary('<serial>')` på landningssidan |
| **Sensordata** | ✅ Bekräftat | `POST /pool/poolSummary` med `serial=<n>` → **HTML** som parsas till alla mätvärden |
| Styr-kommandon | ⏳ Kvar | Fångas via DevTools (se nedan) |

Datasvaret är alltså **HTML** (inte JSON) — pluginen parsar det i `_map_cloud_response()`
i [`api.py`](custom_components/intellipool/api.py), regressionstestat i
[`tests/test_summary_parser.py`](tests/test_summary_parser.py).

---

## Fånga styr-kommandona (återstår för att kunna styra)

När du vill kunna **styra** poolen (inte bara läsa av) behöver kommando-anropen fångas:

1. Öppna [intellipool.eu](https://www.intellipool.eu), logga in, tryck **Cmd+Option+I**
   (Mac) / **F12** → fliken **Network**
2. Bocka i **Preserve log**, filtrera på `XHR`
3. Tryck en styrknapp i gränssnittet (t.ex. tänd belysning, ändra ett börvärde)
4. Notera anropet som dyker upp: **Request URL**, **Method**, och **payload**
   (troligen `/pool/ajax…` eller liknande med `serial=` + kommandoparametrar)

Enklast via Console: kör `funktionsnamn.toString()` på styrfunktionen (som vi gjorde
med `displaySummary`) så syns exakt URL och parametrar. Klistra in i ett
[GitHub-issue](https://github.com/beolink/ha-intellipool/issues) så bygger vi in
`send_command()` och `CLOUD_COMMAND_PATH`.

> **Tips:** *Copy → Copy as cURL* på ett anrop fångar URL + payload på en gång.
> Delar du en HAR-fil: ta bort `PHPSESSID`-cookien och lösenordet först.

### Avancerat: äkta lokal styrning via trafik-proxy

Vill du ändå ha *lokal* kontroll trots molnberoendet kan du tvinga enhetens
utgående trafik genom en maskin du styr:

1. Peka enhetens DNS för `intellipool.eu` mot din egen server (via router/Pi-hole)
2. Kör [mitmproxy](https://mitmproxy.org/) för att se/omdirigera dess HTTPS-anrop
3. Bygg en lokal tjänst som svarar/vidarebefordrar

Detta är avsevärt mer avancerat (enheten kan cert-pinna, och det är skört vid
firmware-uppdateringar). För de flesta är molnvägen den praktiska lösningen.

---

## Felsökning

### Aktivera debug-loggning

Lägg till i `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.intellipool: debug
```

### Vanliga fel

| Fel | Orsak | Lösning |
|---|---|---|
| `endpoint_not_found` | Enheten har ingen lokal server (gäller INTP-1010B) | Använd molnanslutning istället |
| `cannot_connect` | Enheten/molnet är inte nåbart | Kontrollera IP resp. internet |
| `invalid_auth` | Fel lösenord | Kontrollera uppgifterna |

### Visa rådata

I HA-loggarna (med debug aktiverat) syns alla råsvar under nycklarna
`Intellipool local raw data:` respektive `Intellipool cloud raw data:`.
Kopiera detta och lägg upp i ett GitHub-issue så kan vi lägga till stöd
för ditt specifika dataformat.

---

## Arkitektur

```
custom_components/intellipool/
├── __init__.py          ← Integration setup och entry lifecycle
├── manifest.json        ← HA integration manifest
├── config_flow.py       ← UI config flow (lokal / moln)
├── coordinator.py       ← DataUpdateCoordinator (polling var 30s)
├── discovery.py         ← Aktiv nätverkssökning (subnät + hostnamn + fingerprint)
├── api.py               ← API-klient (IntelliPoolLocalAPI / CloudAPI)
├── const.py             ← Konstanter och nyckelnamn
├── sensor.py            ← Mätvärden (temp, pH, ORP, pump...)
├── switch.py            ← Styrning (pump, värme, ljus, AUX...)
├── climate.py           ← Poolvärmning som climate-entitet
├── number.py            ← Börvärden (pH, ORP)
└── translations/
    ├── sv.json          ← Svenska UI-texter
    └── en.json          ← Engelska UI-texter
```

---

## Bidra

Pull requests välkomnas! Speciellt:
- Verifierade API-endpoints för INTP-1010B
- Stöd för E-Box och Intellipool Lite
- Tester

---

## Licens

MIT
