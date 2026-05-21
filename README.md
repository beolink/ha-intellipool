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

### Lokal anslutning

1. Ta reda på din INTP-1010B:s IP-adress (se routerns DHCP-lista eller Intellipool-appen)
2. Välj **Lokal anslutning** i config-flödet
3. Ange IP-adress (t.ex. `192.168.1.45`)
4. Lämna port på `80` (eller testa `8080` / `443` om det inte fungerar)
5. Om controllern kräver autentisering — ange användarnamn och lösenord

> **OBS:** Intellipool INTP-1010B har inget officiellt dokumenterat lokalt API.
> Se avsnittet "Protokoll-discovery" nedan om integrationen inte hittar någon endpoint automatiskt.

### Molnanslutning

1. Välj **Molnanslutning** i config-flödet
2. Ange din e-postadress och lösenord för intellipool.eu
3. Pool-ID identifieras automatiskt (eller ange manuellt)

---

## Protokoll-discovery (VIKTIGT för lokal anslutning)

Eftersom INTP-1010B:s lokala API inte är officiellt dokumenterat måste du hjälpa integrationen
att hitta rätt endpoint. Följ dessa steg:

### Steg 1 – Hitta enhetens IP

```bash
# Pinga nätverket och leta efter enheten
nmap -sP 192.168.1.0/24 | grep -i pentair
# eller kolla routerns DHCP-tabell
```

### Steg 2 – Skanna öppna portar

```bash
nmap -p 80,443,8080,8443,10000,6681 192.168.1.X
```

### Steg 3 – Sniffa HTTP-trafiken med mitmproxy

Det enklaste sättet att se vad controllern skickar:

```bash
# Installera mitmproxy
pip install mitmproxy

# Starta proxy på port 8080
mitmproxy --mode transparent --showhost

# Konfigurera routern att skicka controllerns trafik via proxyn
# (eller konfigurera DNS för att fånga intellipool.eu-trafik)
```

### Steg 4 – Alternativt: Wireshark på routern

```bash
# Om du har OpenWrt/DD-WRT på routern:
tcpdump -i br-lan host 192.168.1.X -w /tmp/intellipool.pcap
# Analysera sedan med Wireshark
```

### Steg 5 – Webbläsarens DevTools

Logga in på [intellipool.eu](https://www.intellipool.eu) i Chrome/Firefox,
öppna DevTools → Nätverk, och titta på vilka HTTP-anrop som görs.
De API-anropen kommunicerar antingen direkt med din controller eller
vidarebefordrar kommandon till den.

### Steg 6 – Uppdatera integrationen

När du hittat rätt endpoint och dataformat, uppdatera `_map_local_response()`
i `custom_components/intellipool/api.py` med rätt nyckelnamn och rapportera gärna
tillbaka så kan vi förbättra integrationen för alla!

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
| `endpoint_not_found` | Ingen känd API-endpoint svarar | Se protokoll-discovery ovan |
| `cannot_connect` | Controllern är inte nåbar | Kontrollera IP och nätverk |
| `invalid_auth` | Fel lösenord | Kontrollera uppgifterna |

### Visa rådata från controllern

I HA-loggarna (med debug aktiverat) syns alla råsvar under nyckeln
`Intellipool local raw data:`. Kopiera detta och lägg upp i ett GitHub-issue
så kan vi lägga till stöd för ditt specifika dataformat.

---

## Arkitektur

```
custom_components/intellipool/
├── __init__.py          ← Integration setup och entry lifecycle
├── manifest.json        ← HA integration manifest
├── config_flow.py       ← UI config flow (lokal / moln)
├── coordinator.py       ← DataUpdateCoordinator (polling var 30s)
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
