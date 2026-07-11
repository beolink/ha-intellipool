"""Validate the cloud WRITE paths (controls + setpoints) offline.

Both are checked against ground truth captured from the live intellipool.eu app
on 2026-07-11 (pool serial 35558):
  - the control body is byte-identical to the live-verified light-toggle request
  - the setpoint body is byte-identical to the app's own jQuery form.serialize()

Standalone:  python3 tests/test_write_paths.py
"""
import importlib.util
import os
import sys
import types

HERE = os.path.dirname(__file__)
ROOT = os.path.dirname(HERE)


def _load_api():
    aiohttp = types.ModuleType("aiohttp")

    class _CT:
        def __init__(self, *a, **k):
            pass

    aiohttp.ClientTimeout = _CT
    aiohttp.ClientSession = object
    aiohttp.ClientError = Exception
    aiohttp.ClientConnectionError = Exception
    aiohttp.ClientConnectorError = Exception
    aiohttp.BasicAuth = lambda *a, **k: None
    aiohttp.TCPConnector = lambda *a, **k: None
    sys.modules["aiohttp"] = aiohttp
    pkg = types.ModuleType("intellipool")
    pkg.__path__ = [os.path.join(ROOT, "custom_components", "intellipool")]
    sys.modules["intellipool"] = pkg

    def load(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        return mod

    base = os.path.join(ROOT, "custom_components", "intellipool")
    load("intellipool.const", os.path.join(base, "const.py"))
    return load("intellipool.api", os.path.join(base, "api.py"))


# --- Ground truth captured live from intellipool.eu ---

COMMANDS_GET_XML = """<root>
    <datas>
        <filtration>1</filtration>
        <filtration_mode>1</filtration_mode>
        <filtration_speed>1</filtration_speed>
        <lighting>2</lighting>
        <type_aux1>2</type_aux1>
        <aux1>2</aux1>
        <heating_regulation>1</heating_regulation>
        <ph_regulation>1</ph_regulation>
        <orp_regulation>0</orp_regulation>
    </datas>
</root>"""

# The exact body the browser POSTed to /pool/ajaxCommands/save to turn the light
# ON (lighting=0), which returned <status>Command was sent</status>.
LIGHT_ON_BODY = (
    "serial=35558&filtration=1&lighting=0&type_aux1=2"
    "&heating_regulation=1&ph_regulation=1&orp_regulation=0&aux1_3p=2"
)

SETPOINTS_GET_XML = """<root>
  <datas expert_mode="false">
    <select>
      <pool_volume>100</pool_volume>
      <setpoint_heating>25</setpoint_heating>
      <type_aux1>2</type_aux1>
      <filling_time>300</filling_time>
      <setpoint_ph>7</setpoint_ph>
      <ph_type>1</ph_type>
      <injection_time_ph>15</injection_time_ph>
      <volume_max_ph>0.1</volume_max_ph>
      <threshold_stop_ph>3</threshold_stop_ph>
      <setpoint_orp>550</setpoint_orp>
      <type_orp>0</type_orp>
      <injection_time_ORP>60</injection_time_ORP>
      <volume_max_ORP>0.1</volume_max_ORP>
      <threshold_stop_ORP>1</threshold_stop_ORP>
      <orp_compensation>0</orp_compensation>
      <freeze_out>3</freeze_out>
      <eco_mode>35</eco_mode>
      <turbo_mode>60</turbo_mode>
      <FILTRATION_WASH_TIME>30</FILTRATION_WASH_TIME>
      <OMEOTECH_FILTRATION_TIME_BEFORE_ALERT>5000</OMEOTECH_FILTRATION_TIME_BEFORE_ALERT>
      <hourstart>0</hourstart>
      <hourend>23</hourend>
      <color_choice>0</color_choice>
      <tempo_aux1>0</tempo_aux1>
      <orp_volume_weekly_10m3>19.9</orp_volume_weekly_10m3>
      <orp_liter_hour_pump>10</orp_liter_hour_pump>
      <OMEOTECH_ORP_VOLUME_TIMER>10</OMEOTECH_ORP_VOLUME_TIMER>
    </select>
    <checkbox>
      <ph_priority>false</ph_priority>
      <orp_priority>false</orp_priority>
      <heating_priority>false</heating_priority>
      <OMEOTECH_PROPORTIONAL_PH>false</OMEOTECH_PROPORTIONAL_PH>
      <OMEOTECH_PROPORTIONAL_CHLORINE>false</OMEOTECH_PROPORTIONAL_CHLORINE>
      <OMEOTECH_HEAT_ONLY_FILTRATION_SCHEDULE>true</OMEOTECH_HEAT_ONLY_FILTRATION_SCHEDULE>
      <OMEOTECH_LIGHTING_FLAG_COVER>false</OMEOTECH_LIGHTING_FLAG_COVER>
      <OMEOTECH_FROST_PROTECT_AIR_TEMP>false</OMEOTECH_FROST_PROTECT_AIR_TEMP>
    </checkbox>
    <timer>
      <timer_aux1>000000000000000000000000</timer_aux1>
      <timer_filtration>111111111111111111111111</timer_filtration>
      <timer_lighting>000000000000000000000000</timer_lighting>
    </timer>
  </datas>
</root>"""

# The exact string the app's own $('#setpoints_35558 > form').serialize() produced.
SETPOINTS_SERIALIZE = (
    "pool_volume=100&setpoint_heating=25&FILTRATION_STOP_DELAY=0"
    "&OMEOTECH_HEAT_ONLY_FILTRATION_SCHEDULE=on&type_aux1=2"
    "&timer_aux1=000000000000000000000000&tempo_aux1=0&setpoint_ph=7&ph_type=1"
    "&injection_time_ph=15&volume_max_ph=0.1&threshold_stop_ph=3&setpoint_orp=550"
    "&type_orp=0&injection_time_ORP=60&volume_max_ORP=0.1&threshold_stop_ORP=1"
    "&orp_volume_weekly_10m3=19.9&orp_liter_hour_pump=10&freeze_out=3"
    "&FILTRATION_WASH_TIME=30&FILTRATION_RINSE_TIME=60"
    "&OMEOTECH_FILTRATION_TIME_BEFORE_ALERT=5000"
    "&timer_filtration=111111111111111111111111&hourstart=0&hourend=23"
    "&color_choice=0&timer_lighting=000000000000000000000000"
)


def test_control_body_matches_live():
    api = _load_api()
    state = api._parse_datas_flat(COMMANDS_GET_XML)
    body = api.build_command_body("35558", state, "light", True)
    assert body == LIGHT_ON_BODY, f"\n got: {body}\nwant: {LIGHT_ON_BODY}"


def test_control_off_maps_correctly():
    api = _load_api()
    state = api._parse_datas_flat(COMMANDS_GET_XML)
    # pump off → filtration=2
    assert "filtration=2" in api.build_command_body("35558", state, "pump", False)
    # heating on → heating_regulation=0 (Auto)
    assert "heating_regulation=0" in api.build_command_body("35558", state, "heating", True)


def test_raw_mode_body():
    """Filtration select → Timer (raw value 3), other fields preserved."""
    api = _load_api()
    state = api._parse_datas_flat(COMMANDS_GET_XML)
    body = api.build_command_body_raw("35558", state, "filtration", "3")
    assert body == (
        "serial=35558&filtration=3&lighting=2&type_aux1=2"
        "&heating_regulation=1&ph_regulation=1&orp_regulation=0&aux1_3p=2"
    ), body


def test_setpoint_body_matches_app_serialize():
    api = _load_api()
    state = api._parse_setpoint_state(SETPOINTS_GET_XML)
    body = api.build_setpoint_body(state)
    assert body == SETPOINTS_SERIALIZE, (
        f"\n got: {body}\nwant: {SETPOINTS_SERIALIZE}"
    )


def test_setpoint_override_changes_only_target():
    api = _load_api()
    state = api._parse_setpoint_state(SETPOINTS_GET_XML)
    body = api.build_setpoint_body(state, overrides={"setpoint_heating": "26"})
    # Exactly one field differs from the app baseline.
    assert body == SETPOINTS_SERIALIZE.replace(
        "setpoint_heating=25", "setpoint_heating=26"
    )


def test_schedule_override_changes_only_timer():
    api = _load_api()
    state = api._parse_setpoint_state(SETPOINTS_GET_XML)
    new = "111111000000000000111111"
    body = api.build_setpoint_body(state, overrides={"timer_filtration": new})
    assert body == SETPOINTS_SERIALIZE.replace(
        "timer_filtration=111111111111111111111111", f"timer_filtration={new}"
    )


INTELLIFLO_GET_XML = """<root><datas>
<speed_range_min>700</speed_range_min>
<speed_range_max>3000</speed_range_max>
<electrolysis_filtration_speed>1500</electrolysis_filtration_speed>
<heating_filtration_speed>700</heating_filtration_speed>
<mode_choc_speed>1500</mode_choc_speed>
<aux1_filtration_speed>2700</aux1_filtration_speed>
<aux2_filtration_speed>0</aux2_filtration_speed>
<aux3_filtration_speed>0</aux3_filtration_speed>
<aux4_filtration_speed>0</aux4_filtration_speed>
<setpoint_intelliflo_speed>3000</setpoint_intelliflo_speed>
</datas></root>"""

INTELLIFLO_SERIALIZE = (
    "speed_range_min=700&speed_range_max=3000&electrolysis_filtration_speed=1500"
    "&heating_filtration_speed=700&mode_choc_speed=1500&FILTRATION_SETPOINT_AIRTEMP=0"
    "&aux1_filtration_speed=2700&aux2_filtration_speed=0&aux3_filtration_speed=0"
    "&aux4_filtration_speed=0&setpoint_intelliflo_speed=3000&sequence_duration=30"
)


def test_intelliflo_body_matches_app_serialize():
    api = _load_api()
    state = api._parse_datas_flat(INTELLIFLO_GET_XML)
    assert api.build_intelliflo_body(state) == INTELLIFLO_SERIALIZE


def test_intelliflo_override_changes_only_target():
    api = _load_api()
    state = api._parse_datas_flat(INTELLIFLO_GET_XML)
    body = api.build_intelliflo_body(
        state, overrides={"setpoint_intelliflo_speed": "2400"}
    )
    assert body == INTELLIFLO_SERIALIZE.replace(
        "setpoint_intelliflo_speed=3000", "setpoint_intelliflo_speed=2400"
    )


if __name__ == "__main__":
    test_control_body_matches_live()
    test_control_off_maps_correctly()
    test_raw_mode_body()
    test_setpoint_body_matches_app_serialize()
    test_setpoint_override_changes_only_target()
    test_schedule_override_changes_only_timer()
    test_intelliflo_body_matches_app_serialize()
    test_intelliflo_override_changes_only_target()
    print("All write-path tests passed (control + setpoint bodies match ground truth).")
