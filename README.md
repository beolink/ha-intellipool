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
| `sensor` | Salthalt | g/L |
| `sensor` | Pumphastighet | % |
| `sensor` | Pumpflöde | m³/h |
| `sensor` | Pumpeffekt | W |
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

### Molnanslutning (rekommenderat för INTP-1010B)

1. Välj **Molnanslutning** i config-flödet
2. Ange din e-postadress och lösenord för intellipool.eu
3. Pool-ID identifieras automatiskt (eller ange manuellt)

> **Status:** Login-flödet är verifierat och fungerar. Data- och kommando-endpointsen
> ligger bakom en inloggad session och måste fångas en gång via DevTools — se nedan.
> Tills dess är moln-data-hämtningen inte fullständig.

---

## Fånga moln-API:et (engångsjobb för full funktion)

`intellipool.eu` är en äldre **PHP-app bakom nginx** (jQuery 1.7.2 + w2ui). Det vi vet:

**Bekräftat (inbyggt i pluginen):**
- **Login:** `POST https://www.intellipool.eu/pool/poolLogin/login`
  med form-fälten `login` (e-post) och `pass` (lösenord), klartext över HTTPS
- **Session:** en `PHPSESSID`-cookie sätts och gäller för alla efterföljande anrop
- **AJAX-mönster:** appen använder `/pool/ajax<Controller>/<action>`
  (t.ex. `/pool/ajaxCreateAccount/checkValidEmail`, `/pool/ajaxEula/getLastText`)

**Måste fångas en gång (kräver din inloggade session):** de exakta
data- och kommando-endpointsen samt deras JSON-format.

### Recept (2 minuter i Chrome/Firefox)

1. Öppna [intellipool.eu](https://www.intellipool.eu) och tryck **F12** → fliken **Network**
2. Bocka i **Preserve log** (Behåll logg)
3. Logga in och öppna din pool-vy så att mätvärdena visas
4. Filtrera på `ajax` (eller `XHR`) i Network-listan
5. Klicka på anropen och notera för var och en:
   - **Request URL** (t.ex. `/pool/ajaxPool/getData?id_key=...`)
   - **Method** (GET/POST) och **payload/parametrar** (särskilt `id_key` eller `serial`)
   - **Response** (JSON) — nyckelnamnen för pH, ORP/redox, temperatur, pump osv.
6. Tryck på en styrknapp (t.ex. tänd belysning) och fånga **kommando-anropet** på samma sätt

Klistra sedan in dessa i ett [GitHub-issue](https://github.com/beolink/ha-intellipool/issues)
eller uppdatera själv:
- `CLOUD_DATA_PATH`, `CLOUD_COMMAND_PATH`, `CLOUD_POOL_LIST_PATH` i
  [`const.py`](custom_components/intellipool/const.py)
- nyckelnamnen i `_map_cloud_response()` i
  [`api.py`](custom_components/intellipool/api.py)

> **Tips:** Högerklicka på ett anrop i DevTools → *Copy → Copy as cURL* fångar
> URL, headers och payload på en gång. Exportera hela sessionen med
> *Save all as HAR* om du vill dela allt (ta bort `PHPSESSID`-cookien och
> ditt lösenord först — de finns i HAR-filen).

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
