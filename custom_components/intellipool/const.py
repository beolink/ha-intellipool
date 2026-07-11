"""Constants for the Pentair Intellipool integration."""
from __future__ import annotations

DOMAIN = "intellipool"
MANUFACTURER = "Pentair"
MODEL = "Intellipool INTP-1010B"

# Connection types
CONN_TYPE_LOCAL = "local"
CONN_TYPE_CLOUD = "cloud"
CONN_TYPE_OFFICIAL = "official"

# Config entry keys
CONF_CONNECTION_TYPE = "connection_type"
CONF_HOST = "host"
CONF_PORT = "port"
CONF_SSL = "ssl"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_POOL_ID = "pool_id"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_API_KEY = "api_key"          # official domotique-piscine.eu API key
CONF_INSTALL_ID = "install_id"    # official API installation id
CONF_STALE_MINUTES = "stale_minutes"  # failsafe threshold

# Defaults
DEFAULT_PORT = 80
DEFAULT_SCAN_INTERVAL = 30
DEFAULT_SSL = False
DEFAULT_STALE_MINUTES = 30

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

# --- Control + setpoint endpoints: CONFIRMED via authenticated DevTools session ---
# (control write live-verified against a real INTP-1010B on 2026-07-11)
CLOUD_POOL_LIST_PATH = "/pool/poolList/group"    # authenticated landing/list page
CLOUD_COMMANDS_GET = "/pool/ajaxCommands/get"    # GET  serial= → XML <datas>
CLOUD_COMMANDS_SAVE = "/pool/ajaxCommands/save"  # POST serial=&<fields> (actuates)
CLOUD_SETPOINTS_GET = "/pool/ajaxSetpoints/get"  # GET  serial= → XML <datas>
CLOUD_SETPOINTS_SAVE = "/pool/ajaxSetpoints/save"  # POST serial=&<form> (actuates)
CLOUD_ORDER_PATH = "/pool/ajaxOmeoGetCurrentsOrder"  # GET serial= → <order .../>
CLOUD_COMMAND_PATH = CLOUD_COMMANDS_SAVE         # back-compat alias

# The exact field set the commands save form submits (order matters for parity).
# aux1 is sent as aux1_3p when type_aux1 != 0, else aux1_2p (handled in code).
# (CONTROL_FIELD_MAP / SETPOINT_FIELD_MAP are defined below, after the KEY_* names.)
CLOUD_COMMAND_SAVE_FIELDS = [
    "filtration", "lighting", "type_aux1", "heating_regulation",
    "ph_regulation", "orp_regulation",
]

# The setpoints save form, in exact submit order. Each entry: (name, kind).
# kind: "select"/"timer" → value from ajaxSetpoints/get; "checkbox" → included
# only when the /get value is true (submitted as "on"); "const" → fixed default
# that the form supplies but /get does not. Validated byte-for-byte against the
# app's own jQuery form.serialize() output (see tests/test_setpoints_writer.py).
SETPOINT_FORM_SPEC = [
    ("pool_volume", "select"),
    ("setpoint_heating", "select"),
    ("FILTRATION_STOP_DELAY", "const:0"),
    ("OMEOTECH_HEAT_ONLY_FILTRATION_SCHEDULE", "checkbox"),
    ("heating_priority", "checkbox"),
    ("type_aux1", "select"),
    ("timer_aux1", "timer"),
    ("tempo_aux1", "select"),
    ("setpoint_ph", "select"),
    ("ph_type", "select"),
    ("injection_time_ph", "select"),
    ("volume_max_ph", "select"),
    ("threshold_stop_ph", "select"),
    ("OMEOTECH_PROPORTIONAL_PH", "checkbox"),
    ("setpoint_orp", "select"),
    ("type_orp", "select"),
    ("injection_time_ORP", "select"),
    ("volume_max_ORP", "select"),
    ("threshold_stop_ORP", "select"),
    ("orp_volume_weekly_10m3", "select"),
    ("orp_liter_hour_pump", "select"),
    ("OMEOTECH_PROPORTIONAL_CHLORINE", "checkbox"),
    ("freeze_out", "select"),
    ("OMEOTECH_FROST_PROTECT_AIR_TEMP", "checkbox"),
    ("FILTRATION_WASH_TIME", "select"),
    ("FILTRATION_RINSE_TIME", "const:60"),
    ("OMEOTECH_FILTRATION_TIME_BEFORE_ALERT", "select"),
    ("timer_filtration", "timer"),
    ("hourstart", "select"),
    ("hourend", "select"),
    ("color_choice", "select"),
    ("OMEOTECH_LIGHTING_FLAG_COVER", "checkbox"),
    ("timer_lighting", "timer"),
]

# ---------------------------------------------------------------------------
# Official API (api.domotique-piscine.eu) — the backend behind intellipool.eu.
# Clean, key-based REST. Fewer values than the scrape, but reliable → we use it
# as a FAILSAFE fallback (and it can also be used standalone).
#   GET /api/install/<install_id>/probes?key=<api_key>  → JSON {"values":[...]}
# Each value: {"typeInfo": <KEY>, "value": <str>, "unit": <str optional>}
# ---------------------------------------------------------------------------
OFFICIAL_BASE_URL = "https://api.domotique-piscine.eu"
OFFICIAL_PROBES_PATH = "/api/install/{install_id}/probes"
OFFICIAL_KEY_PARAM = "key"

# typeInfo → (PoolData field, kind) ; kind: "float" | "bool" | "text"
OFFICIAL_FIELD_MAP = {
    "WATER_TEMP": ("water_temperature", "float"),
    "AIR_TEMP": ("air_temperature", "float"),
    "PH": ("ph", "float"),
    "ORP": ("orp", "float"),
    "CONDUCTIVITY": ("salinity", "float"),
    "OMEOTECH_FLAG_FILTRATION": ("filtration", "bool"),
    "OMEOTECH_FLAG_HEATING": ("heating", "bool"),
    "OMEOTECH_FLAG_LIGHTING": ("light", "bool"),
    "OMEOTECH_FLAG_AUX1": ("aux_1", "bool"),
    "OMEOTECH_FLAG_AUX2": ("aux_2", "bool"),
    "OMEOTECH_FLAG_AUX3": ("aux_3", "bool"),
    "OMEOTECH_FLAG_CHLORINATION": ("chlorinator", "bool"),
    "DATETIME": ("updated", "text"),
}

# Data source labels (exposed as a diagnostic sensor)
SOURCE_PRIMARY = "primary"
SOURCE_FALLBACK = "fallback"
KEY_DATA_SOURCE = "data_source"

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

# ---------- Cloud write mappings (defined here, after the KEY_* names) ----------
# Control value semantics decoded from the control panel image labels.
# HA key → (device field, {True: on_value, False: off_value})
CONTROL_FIELD_MAP = {
    KEY_PUMP: ("filtration", {True: "1", False: "2"}),        # 0=Auto 1=On 2=Off 3=Timer 4=Choc
    KEY_FILTRATION: ("filtration", {True: "1", False: "2"}),
    KEY_LIGHT: ("lighting", {True: "0", False: "2"}),         # 0=On 1=Timer 2=Off
    KEY_HEATING: ("heating_regulation", {True: "0", False: "1"}),   # 0=Auto 1=Off
    KEY_PH_DOSING: ("ph_regulation", {True: "0", False: "1"}),
    KEY_ORP_DOSING: ("orp_regulation", {True: "0", False: "1"}),
    KEY_CHLORINATOR: ("orp_regulation", {True: "0", False: "1"}),
    KEY_AUX_1: ("aux1", {True: "0", False: "2"}),            # 0=On 1=Schedule 2=Off
}

# HA setpoint key → device setpoint field
SETPOINT_FIELD_MAP = {
    KEY_TARGET_TEMP: "setpoint_heating",
    KEY_TARGET_PH: "setpoint_ph",
    KEY_TARGET_ORP: "setpoint_orp",
}

# Select entities: full mode selectors (value → label), written as raw control
# values via /pool/ajaxCommands/save. Current mode is read from command_state.
FILTRATION_MODES = {"0": "Auto", "1": "På", "2": "Av", "3": "Timer", "4": "Chock"}
LIGHTING_MODES = {"0": "På", "1": "Timer", "2": "Av"}

# HA select command key → (device field, value→label map)
RAW_CONTROL_MAP = {
    "filtration_mode": ("filtration", FILTRATION_MODES),
    "lighting_mode": ("lighting", LIGHTING_MODES),
}

# Schedule (24-char, one char per hour, 0/1) text entities → setpoints timer field
SCHEDULE_FIELD_MAP = {
    "schedule_filtration": "timer_filtration",
    "schedule_lighting": "timer_lighting",
    "schedule_aux1": "timer_aux1",
}

# --- IntelliFlo variable-speed pump ---
CLOUD_INTELLIFLO_GET = "/pool/ajaxIntelliFlo/get"    # POST serial= → XML <datas>
CLOUD_INTELLIFLO_SAVE = "/pool/ajaxIntelliFlo/save"  # POST serial=&<form>

# IntelliFlo save form, exact submit order. ("get" → value from /get;
# "const:X" → form default not present in /get). Validated byte-for-byte against
# the app's own form.serialize() in tests.
INTELLIFLO_FORM_SPEC = [
    ("speed_range_min", "get"),
    ("speed_range_max", "get"),
    ("electrolysis_filtration_speed", "get"),
    ("heating_filtration_speed", "get"),
    ("mode_choc_speed", "get"),
    ("FILTRATION_SETPOINT_AIRTEMP", "const:0"),
    ("aux1_filtration_speed", "get"),
    ("aux2_filtration_speed", "get"),
    ("aux3_filtration_speed", "get"),
    ("aux4_filtration_speed", "get"),
    ("setpoint_intelliflo_speed", "get"),
    ("sequence_duration", "const:30"),
]

# HA number key → device IntelliFlo speed field (RPM). Speeds snap to 20-rpm
# steps and are bounded by speed_range_min/max.
INTELLIFLO_SPEED_MAP = {
    "speed_setpoint": "setpoint_intelliflo_speed",
    "speed_electrolysis": "electrolysis_filtration_speed",
    "speed_heating": "heating_filtration_speed",
    "speed_aux1": "aux1_filtration_speed",
    "speed_choc": "mode_choc_speed",
}
INTELLIFLO_SPEED_STEP = 20

# --- Historic backfill (long-term statistics import) ---
# GET /pool/ajaxHistoric/getJsonValues?serial=&date=<Y-m-d>&type_date=DAY|MONTH|YEAR
# → {status, typeDate, records:[{typeInfo, values[], min, max, avg}]}
# DAY gives hourly values (index = hour). Session-based (cloud only).
CLOUD_HISTORY_PATH = "/pool/ajaxHistoric/getJsonValues"

# Historic typeInfo → sensor description key (statistics land on that sensor).
HISTORY_SENSOR_MAP = {
    "WATER_TEMP": "water_temperature",
    "AIR_TEMP": "air_temperature",
    "PH": "ph",
    "ORP": "orp",
    "CONDUCTIVITY": "salinity",
    "PENTAIR_FILTRATION_POWER": "pump_power",
    "PENTAIR_FILTRATION_PUMP_RPM": "pump_speed",
    "BATTERY_PEROK": "battery_voltage",
    "RSSI": "signal_strength",
}

SERVICE_IMPORT_HISTORY = "import_history"
ATTR_DAYS = "days"
DEFAULT_HISTORY_DAYS = 7
