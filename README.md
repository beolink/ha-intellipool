# Pentair Intellipool for Home Assistant

[![hacs][hacs-badge]][hacs-url]
[![release][release-badge]][release-url]

Home Assistant integration for **Pentair Intellipool** pool controllers
(developed and verified against the **INTP-1010B**).

Monitor water temperature, pH, ORP, salinity and pump metrics — and control
filtration, heating, lighting, dosing, IntelliFlo pump speeds, setpoints and
schedules. Historic values can be backfilled into Home Assistant's long-term
statistics.

> **Unofficial.** Not affiliated with, endorsed by, or supported by Pentair.
> Intellipool exposes no public API, so this integration talks to the same
> endpoints the official web app uses. Those are undocumented and may change
> without notice.

---

## Entities

| Platform | Entity | Notes |
|---|---|---|
| `sensor` | Water temperature | °C |
| `sensor` | Air temperature | °C |
| `sensor` | pH | |
| `sensor` | ORP (redox) | mV |
| `sensor` | Salinity (conductivity) | g/L |
| `sensor` | Filtration speed | rpm |
| `sensor` | Pump flow | m³/h |
| `sensor` | Pump power | W |
| `sensor` | Sensor battery | V, diagnostic |
| `sensor` | Radio signal | dB, diagnostic |
| `sensor` | Status message | diagnostic |
| `sensor` | Data source | `primary` / `fallback`, diagnostic |
| `switch` | Pump, Filtration, Heating, Lighting | on/off |
| `switch` | Chlorination, pH dosing, ORP dosing | on/off |
| `switch` | Aux 1–3 | auxiliary outputs |
| `select` | Filtration mode | Auto / On / Off / Timer / Boost |
| `select` | Lighting mode | On / Timer / Off |
| `climate` | Pool heating | target temperature |
| `number` | pH setpoint | 6.8–7.8 |
| `number` | ORP setpoint | 200–800 mV |
| `number` | IntelliFlo speeds | setpoint / electrolysis / heating / aux 1 / boost, rpm in steps of 20 |
| `text` | Filtration / lighting / aux 1 schedule | 24 characters, one digit per hour (`0`/`1`) |

Entity names are translated; English and Swedish are included.

---

## Installation

### HACS (recommended)

1. HACS → ⋮ → **Custom repositories**
2. Repository: `https://github.com/beolink/ha-intellipool`, category **Integration**
3. Find **Pentair Intellipool** in HACS and download it
4. Restart Home Assistant
5. **Settings → Devices & Services → Add Integration → Intellipool**

### Manual

```bash
cp -r custom_components/intellipool /config/custom_components/
```

Restart Home Assistant, then add the integration as above.

---

## Configuration

### Connection types

| Type | Source | Values | Notes |
|---|---|---|---|
| **Cloud** *(recommended)* | intellipool.eu (web app) | All sensors, controls and setpoints | Needs your intellipool.eu login |
| **Official API** | api.domotique-piscine.eu | Fewer (temperatures, pH, ORP, salinity, flags) | Key-based, read-only, very reliable |
| **Local** | Device IP | — | Not usable on the INTP-1010B, see below |

### ⚠️ The INTP-1010B has no local server

Verified empirically against a real device:

| Test | Result |
|---|---|
| ARP (layer 2) | ✅ Device responds — MAC OUI `00:0B:3C` (Cygnal / Silicon Labs) |
| ICMP ping | ❌ Blocked |
| **All 65535 TCP ports** | ❌ **None open** — every connection silently dropped |
| UDP mDNS / SSDP / discovery beacons | ❌ Device announces nothing |

The controller only makes **outbound** connections to `intellipool.eu`. There is
no local port to connect to, so local polling is impossible on this hardware —
the same is true of most European pool controllers (Hayward, Bayrol).

The local connection type is kept for other or future models that do run a web
server. **For the INTP-1010B, use the cloud connection.**

### Cloud connection

1. Pick **Cloud connection**
2. Enter your intellipool.eu email and password
3. The pool serial is detected automatically, or you can enter it manually
4. *(Optional)* Enter an **installation ID + API key** to enable the failsafe

> **Note on the pool serial:** the number shown as `N°…` in the web app is the
> *display* serial. The API uses a different *raw* serial. The integration
> detects the raw one; if you enter it by hand, use the number from
> `displaySummary('…')` in the pool list page source — not the `N°` number.

### Official API

A clean, key-based REST API (the service behind intellipool.eu). Read-only and
fewer values, but very reliable. Both values are in your REST URL:

```
https://api.domotique-piscine.eu/api/install/<INSTALL-ID>/probe/water-temp?key=<API-KEY>
```

The integration uses the bulk endpoint `/api/install/<id>/probes?key=<key>`
(one request returns every value).

### Failsafe (cloud + official API)

Run the cloud connection as the primary source **with the official API as a
backup**: enter the installation ID and API key in the cloud step.

- Normally the cloud source is used (it has the most values)
- If it **errors** or its timestamp **stops advancing** for more than N minutes
  (default 30, configurable), the integration switches to the official API
- Values only the cloud source provides (pump speed/power, setpoints, battery)
  are carried over from the last good update so those entities stay available
- The **Data source** diagnostic sensor shows `primary` or `fallback`

---

## History import

The **`intellipool.import_history`** service backfills Home Assistant's
long-term statistics with hourly historic values, so older history shows up on
the existing sensor graphs.

- **Developer tools → Actions → `Intellipool: Import history`**, with `days`
  (how many days back, default 7)
- Fetches one day at a time at hourly resolution and writes `mean`/`min`/`max`
  per hour straight onto the sensor (`source: recorder`)
- Requires the **cloud connection**. Imported series: water and air temperature,
  pH, ORP, salinity, pump power and speed, sensor battery, radio signal
- Idempotent — re-importing an hour just rewrites the same value

---

## How it works

`intellipool.eu` is an older PHP app behind nginx (jQuery + w2ui) using a
`PHPSESSID` session. Everything below was found by inspecting the web app and
verified against a real controller.

| Part | Endpoint |
|---|---|
| Login | `POST /pool/poolLogin/login` (`login` + `pass`) |
| Sensor data | `POST /pool/poolSummary` (`serial=`) → **HTML**, parsed |
| Controls | `GET`/`POST /pool/ajaxCommands/get`\|`/save` |
| Setpoints | `GET`/`POST /pool/ajaxSetpoints/get`\|`/save` |
| IntelliFlo | `POST /pool/ajaxIntelliFlo/get`\|`/save` |
| History | `GET /pool/ajaxHistoric/getJsonValues` (`type_date=DAY\|MONTH\|YEAR`) |
| Order ack | `GET /pool/ajaxOmeoGetCurrentsOrder` |

Control values:

| Field | Values |
|---|---|
| `filtration` | 0 = Auto, 1 = On, 2 = Off, 3 = Timer, 4 = Boost |
| `lighting` | 0 = On, 1 = Timer, 2 = Off |
| `heating_regulation`, `ph_regulation`, `orp_regulation` | 0 = Auto, 1 = Off |
| `aux1` | 0 = On, 1 = Schedule, 2 = Off |

**Writes are conservative.** The integration always reads the current state
first and changes only the requested field, then submits the complete form —
byte-identical to what the web app itself sends (verified in
[`tests/test_write_paths.py`](tests/test_write_paths.py)). Nothing else is
touched. Because the controller only reaches the cloud outbound, a change
becomes a queued *order* that the device applies on its next check-in.

---

## Troubleshooting

### Debug logging

```yaml
logger:
  default: warning
  logs:
    custom_components.intellipool: debug
```

### Common errors

| Error | Cause | Fix |
|---|---|---|
| `endpoint_not_found` | The device has no local server (INTP-1010B) | Use the cloud connection |
| `cannot_connect` | Device or cloud unreachable | Check network / internet |
| `invalid_auth` | Wrong credentials | Re-check email and password |
| `no_serial` | Serial could not be auto-detected | Enter the raw serial manually (see note above) |
| Sensors exist but have no values | Wrong pool serial — the scrape returns an empty page | Re-add with the raw serial |

With debug logging on, raw responses are logged so you can attach them to an
issue if your device returns a different format.

---

## Anonymous statistics

The integration sends one report per day to <https://stats.rnet.se>: which
version you run, your Home Assistant version and installation type, the country
you have set in Home Assistant, an approximate position rounded to about 11 km,
which transport is in use (scrape, official API or local) and whether the
failsafe is configured, plus the pool's own readings at reporting time: water
and air temperature, pH, ORP, salinity and pump speed.

Read once a day, never sampled. A pool's chemistry says something about the
pool and nothing about the people, and a daily reading cannot show when anyone
is home. It never sends a name, an address, an exact position, a pool id, a
serial number or an entity name, your IP address is not stored, and a reading
outside a physically sane range is dropped rather than sent. The fleet figures
are public at <https://stats.rnet.se>; the map of where installations run is
not.

To opt out: *Settings, Devices and services, Intellipool, Configure, Send
anonymous usage statistics.* Switching it off also erases what has already been
sent about your installation. The full list of fields and the reasoning:
<https://stats.rnet.se/integritet>. What this integration contributes is
`stats_extra.py`, and the client that sends it is `stats.py`.

## Development

```bash
# Pure logic tests — no dependencies
python3 tests/test_summary_parser.py
python3 tests/test_official_parser.py
python3 tests/test_write_paths.py

# Full Home Assistant pipeline tests
python3.13 -m venv .venv && .venv/bin/pip install -r requirements-test.txt
.venv/bin/pytest tests/test_ha_integration.py tests/test_history_import.py -v
```

The write paths are validated byte-for-byte against captured ground truth from
the real web app, so control and setpoint requests can be changed safely without
touching live equipment.

### Layout

```
custom_components/intellipool/
├── __init__.py        Setup, entry lifecycle, import_history service
├── api.py             API clients (cloud / official / local) + parsers
├── coordinator.py     DataUpdateCoordinator with failsafe
├── config_flow.py     UI configuration
├── const.py           Constants, field maps, form specs
├── discovery.py       Active network scan (local mode)
├── history.py         Long-term statistics backfill
├── sensor.py  switch.py  climate.py  number.py  select.py  text.py
├── services.yaml      Service definitions
├── strings.json       Base strings (English)
└── translations/      en, sv
```

---

## Roadmap

- [x] Cloud sensors with official-API failsafe
- [x] Controls, setpoints, mode selects and schedules
- [x] IntelliFlo variable-speed pump control
- [x] History import into long-term statistics
- [x] Verified in a real Home Assistant instance
- [ ] More reliable raw-serial auto-detection during setup
- [ ] Treat an empty cloud response as a failure so the failsafe takes over
- [ ] Support for E-Box and Intellipool Lite

---

## Contributing

Pull requests are welcome — especially verified endpoints for other Intellipool
models, additional translations, and tests. If your controller returns a
different data format, open an issue with the raw response from debug logs.

## License

[Apache License 2.0](LICENSE). Copyright 2026 Andreas Reimers.

[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[hacs-url]: https://github.com/hacs/integration
[release-badge]: https://img.shields.io/github/v/release/beolink/ha-intellipool
[release-url]: https://github.com/beolink/ha-intellipool/releases
