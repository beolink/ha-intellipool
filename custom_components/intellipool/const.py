"""Constants for the Pentair Intellipool integration."""
from __future__ import annotations

DOMAIN = "intellipool"
MANUFACTURER = "Pentair"
MODEL = "Intellipool INTP-1010B"

# Connection types
CONN_TYPE_LOCAL = "local"
CONN_TYPE_CLOUD = "cloud"

# Config entry keys
CONF_CONNECTION_TYPE = "connection_type"
CONF_HOST = "host"
CONF_PORT = "port"
CONF_SSL = "ssl"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_POOL_ID = "pool_id"
CONF_SCAN_INTERVAL = "scan_interval"

# Defaults
DEFAULT_PORT = 80
DEFAULT_SCAN_INTERVAL = 30
DEFAULT_SSL = False

# Cloud service (intellipool.eu)
# NOTE: intellipool.eu is an older server-rendered jQuery/w2ui web app.
# The login flow below is CONFIRMED from the public login page. The data and
# command paths are NOT yet confirmed — they live behind the authenticated
# session and must be captured with browser DevTools (see README → "Fånga
# moln-API:et"). Update them once captured.
CLOUD_BASE_URL = "https://www.intellipool.eu"

# --- Confirmed from the public login page ---
CLOUD_LOGIN_PATH = "/pool/poolLogin/login"   # POST, form-urlencoded
CLOUD_LOGIN_FIELD_USER = "login"             # username / e-mail field
CLOUD_LOGIN_FIELD_PASS = "pass"              # password field (plaintext over TLS)

# --- Data endpoint: CONFIRMED (captured from the app via DevTools) ---
# POST form-urlencoded "serial=<pool serial>" → returns an HTML summary fragment
# that we parse in api._parse_summary_html().
CLOUD_DATA_PATH = "/pool/poolSummary"
CLOUD_DATA_FIELD_SERIAL = "serial"

# --- Command endpoint: still to be captured (controls come later) ---
CLOUD_COMMAND_PATH = "/pool/poolCommand"     # PLACEHOLDER — capture real path
CLOUD_POOL_LIST_PATH = "/pool/poolListDisplay"  # authenticated landing/list page

# Local device – try these paths in order until one responds
LOCAL_PROBE_PATHS = [
    "/api/v1/status",
    "/api/status",
    "/api/data",
    "/status",
    "/data.json",
    "/state.json",
    "/pool",
    "/cgi-bin/status",
    "/cgi-bin/data",
]
LOCAL_COMMAND_PATHS = [
    "/api/v1/command",
    "/api/command",
    "/command",
    "/set",
    "/cgi-bin/command",
]

# ---------- Sensor data keys ----------
KEY_WATER_TEMP = "water_temperature"
KEY_AIR_TEMP = "air_temperature"
KEY_PH = "ph"
KEY_ORP = "orp"
KEY_SALINITY = "salinity"
KEY_PUMP_SPEED = "pump_speed"        # RPM
KEY_PUMP_FLOW = "pump_flow"          # m³/h
KEY_PUMP_POWER = "pump_power"        # W
KEY_BATTERY_VOLTAGE = "battery_voltage"  # V
KEY_SIGNAL_STRENGTH = "signal_strength"  # dB
KEY_INFO_MESSAGE = "info_message"    # Control Center info/error text

# ---------- Switch / binary keys ----------
KEY_PUMP = "pump"
KEY_HEATING = "heating"
KEY_LIGHT = "light"
KEY_CHLORINATOR = "chlorinator"
KEY_PH_DOSING = "ph_dosing"
KEY_ORP_DOSING = "orp_dosing"
KEY_FILTRATION = "filtration"
KEY_AUX_1 = "aux_1"
KEY_AUX_2 = "aux_2"
KEY_AUX_3 = "aux_3"

# ---------- Setpoint / number keys ----------
KEY_TARGET_TEMP = "target_temperature"
KEY_TARGET_PH = "target_ph"
KEY_TARGET_ORP = "target_orp"

# All keys that can be toggled on/off
SWITCH_KEYS = [
    KEY_PUMP,
    KEY_HEATING,
    KEY_LIGHT,
    KEY_CHLORINATOR,
    KEY_PH_DOSING,
    KEY_ORP_DOSING,
    KEY_FILTRATION,
    KEY_AUX_1,
    KEY_AUX_2,
    KEY_AUX_3,
]
