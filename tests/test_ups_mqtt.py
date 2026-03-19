"""
Unit tests for ups-mqtt.py.

Tests cover the pure logic functions that can run without a NUT daemon or MQTT
broker — topic construction, payload content, UPS data parsing, online detection,
and MQTT callbacks. Network I/O (subprocess, broker connection) is mocked.
"""

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

import ups_mqtt


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FULL_UPS_DATA = {
    "battery.charge":          "100",
    "battery.charge.low":      "10",
    "battery.runtime":         "2340",
    "battery.runtime.low":     "120",
    "battery.voltage":         "27.2",
    "battery.voltage.nominal": "24.0",
    "ups.status":              "OL",
    "ups.load":                "18.5",
    "ups.beeper.status":       "enabled",
    "ups.delay.shutdown":      "20",
}

TS = "2026-03-19T10:00:00Z"


# ---------------------------------------------------------------------------
# MQTT topics
# ---------------------------------------------------------------------------

def test_battery_topic():
    assert ups_mqtt.battery_topic == "atlantis/global/data/rack/raspberrypi5/battery/telemetry"


def test_ups_status_topic():
    assert ups_mqtt.ups_status_topic == "atlantis/global/state/rack/raspberrypi5/ups/status"


def test_avail_topic():
    assert ups_mqtt.avail_topic == "atlantis/global/availability/rack/raspberrypi5/node/status"


# ---------------------------------------------------------------------------
# get_ups_data — upsc output parsing
# ---------------------------------------------------------------------------

def _make_upsc_result(stdout: str) -> MagicMock:
    result = MagicMock()
    result.stdout = stdout
    return result


def test_get_ups_data_parses_key_value_pairs():
    output = "battery.charge: 100\nbattery.voltage: 27.2\nups.status: OL\n"
    with patch("subprocess.run", return_value=_make_upsc_result(output)):
        data = ups_mqtt.get_ups_data()
    assert data["battery.charge"] == "100"
    assert data["battery.voltage"] == "27.2"
    assert data["ups.status"] == "OL"


def test_get_ups_data_strips_whitespace():
    output = "ups.status:  OL  \nbattery.charge:  99  \n"
    with patch("subprocess.run", return_value=_make_upsc_result(output)):
        data = ups_mqtt.get_ups_data()
    assert data["ups.status"] == "OL"
    assert data["battery.charge"] == "99"


def test_get_ups_data_skips_malformed_lines():
    output = "this line has no colon\nbattery.charge: 100\n"
    with patch("subprocess.run", return_value=_make_upsc_result(output)):
        data = ups_mqtt.get_ups_data()
    assert "battery.charge" in data
    assert len(data) == 1


def test_get_ups_data_returns_empty_on_subprocess_exception():
    with patch("subprocess.run", side_effect=OSError("upsc not found")):
        data = ups_mqtt.get_ups_data()
    assert data == {}


def test_get_ups_data_returns_empty_on_empty_output():
    with patch("subprocess.run", return_value=_make_upsc_result("")):
        data = ups_mqtt.get_ups_data()
    assert data == {}


def test_get_ups_data_value_with_colon_in_it():
    # Values that contain a colon (e.g. driver version strings) must be kept intact
    output = "driver.version: 2.8.1-5 (NUT v2.8.1)\n"
    with patch("subprocess.run", return_value=_make_upsc_result(output)):
        data = ups_mqtt.get_ups_data()
    assert data["driver.version"] == "2.8.1-5 (NUT v2.8.1)"


# ---------------------------------------------------------------------------
# is_ups_online
# ---------------------------------------------------------------------------

def test_is_ups_online_ol_status():
    assert ups_mqtt.is_ups_online({"ups.status": "OL"}) is True


def test_is_ups_online_ob_status():
    assert ups_mqtt.is_ups_online({"ups.status": "OB"}) is False


def test_is_ups_online_lb_status():
    assert ups_mqtt.is_ups_online({"ups.status": "LB"}) is False


def test_is_ups_online_ol_lb_combined():
    # OL CHRG LB is a valid combined NUT status — contains OL so online
    assert ups_mqtt.is_ups_online({"ups.status": "OL CHRG LB"}) is True


def test_is_ups_online_missing_key():
    assert ups_mqtt.is_ups_online({}) is False


# ---------------------------------------------------------------------------
# publish_battery — payload content and MQTT call
# ---------------------------------------------------------------------------

def test_publish_battery_publishes_to_correct_topic():
    client = MagicMock()
    ups_mqtt.publish_battery(client, FULL_UPS_DATA, TS)
    assert client.publish.call_count == 1
    topic = client.publish.call_args[0][0]
    assert topic == "atlantis/global/data/rack/raspberrypi5/battery/telemetry"


def test_publish_battery_payload_is_valid_json():
    client = MagicMock()
    ups_mqtt.publish_battery(client, FULL_UPS_DATA, TS)
    payload_str = client.publish.call_args[0][1]
    data = json.loads(payload_str)
    assert isinstance(data, dict)


def test_publish_battery_payload_contains_all_fields():
    client = MagicMock()
    ups_mqtt.publish_battery(client, FULL_UPS_DATA, TS)
    payload = json.loads(client.publish.call_args[0][1])
    values = payload["values"]
    assert values["charge"]          == 100.0
    assert values["charge_low"]      == 10.0
    assert values["runtime"]         == 2340.0
    assert values["runtime_low"]     == 120.0
    assert values["voltage"]         == 27.2
    assert values["voltage_nominal"] == 24.0
    assert payload["timestamp"]      == TS


def test_publish_battery_uses_qos_0_no_retain():
    client = MagicMock()
    ups_mqtt.publish_battery(client, FULL_UPS_DATA, TS)
    kwargs = client.publish.call_args[1]
    assert kwargs["qos"]    == 0
    assert kwargs["retain"] is False


def test_publish_battery_missing_field_does_not_raise():
    client = MagicMock()
    incomplete = {k: v for k, v in FULL_UPS_DATA.items() if k != "battery.charge"}
    ups_mqtt.publish_battery(client, incomplete, TS)  # must not raise
    assert client.publish.call_count == 0  # nothing published on error


def test_publish_battery_invalid_float_does_not_raise():
    client = MagicMock()
    bad_data = {**FULL_UPS_DATA, "battery.charge": "not-a-number"}
    ups_mqtt.publish_battery(client, bad_data, TS)  # must not raise
    assert client.publish.call_count == 0


# ---------------------------------------------------------------------------
# publish_ups_status — payload content and MQTT call
# ---------------------------------------------------------------------------

def test_publish_ups_status_publishes_to_correct_topic():
    client = MagicMock()
    ups_mqtt.publish_ups_status(client, FULL_UPS_DATA, TS)
    topic = client.publish.call_args[0][0]
    assert topic == "atlantis/global/state/rack/raspberrypi5/ups/status"


def test_publish_ups_status_payload_is_valid_json():
    client = MagicMock()
    ups_mqtt.publish_ups_status(client, FULL_UPS_DATA, TS)
    payload_str = client.publish.call_args[0][1]
    data = json.loads(payload_str)
    assert isinstance(data, dict)


def test_publish_ups_status_payload_contains_all_fields():
    client = MagicMock()
    ups_mqtt.publish_ups_status(client, FULL_UPS_DATA, TS)
    data = json.loads(client.publish.call_args[0][1])
    assert data["status"]         == "OL"
    assert data["load"]           == 18.5
    assert data["beeper_status"]  == "enabled"
    assert data["delay_shutdown"] == 20.0
    assert data["timestamp"]      == TS


def test_publish_ups_status_uses_qos_1_retain():
    client = MagicMock()
    ups_mqtt.publish_ups_status(client, FULL_UPS_DATA, TS)
    kwargs = client.publish.call_args[1]
    assert kwargs["qos"]    == 1
    assert kwargs["retain"] is True


def test_publish_ups_status_missing_optional_fields_uses_defaults():
    client = MagicMock()
    # Only ups.status present; load/beeper/delay are optional (fall back to defaults)
    ups_mqtt.publish_ups_status(client, {"ups.status": "OB"}, TS)
    data = json.loads(client.publish.call_args[0][1])
    assert data["status"]         == "OB"
    assert data["load"]           == 0.0
    assert data["beeper_status"]  == ""
    assert data["delay_shutdown"] == 0.0


# ---------------------------------------------------------------------------
# on_connect callback
# ---------------------------------------------------------------------------

def test_on_connect_success_sets_connected_flag():
    ups_mqtt._connected = False
    client = MagicMock()
    ups_mqtt.on_connect(client, None, None, 0, None)
    assert ups_mqtt._connected is True


def test_on_connect_success_publishes_birth_message():
    ups_mqtt._connected = False
    ups_mqtt._logger = None
    client = MagicMock()
    ups_mqtt.on_connect(client, None, None, 0, None)
    assert client.publish.call_count == 1
    topic = client.publish.call_args[0][0]
    assert topic == ups_mqtt.avail_topic
    payload = json.loads(client.publish.call_args[0][1])
    assert payload["status"] == "online"
    assert "timestamp" in payload


def test_on_connect_success_birth_uses_qos_1_retain():
    ups_mqtt._connected = False
    ups_mqtt._logger = None
    client = MagicMock()
    ups_mqtt.on_connect(client, None, None, 0, None)
    kwargs = client.publish.call_args[1]
    assert kwargs["qos"]    == 1
    assert kwargs["retain"] is True


def test_on_connect_failure_does_not_set_connected():
    ups_mqtt._connected = False
    ups_mqtt._logger = None
    client = MagicMock()
    ups_mqtt.on_connect(client, None, None, 5, None)  # reason_code != 0
    assert ups_mqtt._connected is False
    assert client.publish.call_count == 0


# ---------------------------------------------------------------------------
# on_disconnect callback
# ---------------------------------------------------------------------------

def test_on_disconnect_clears_connected_flag():
    ups_mqtt._connected = True
    ups_mqtt._logger = None
    ups_mqtt._shutdown = False
    ups_mqtt.on_disconnect(None, None, None, 0, None)
    assert ups_mqtt._connected is False


# ---------------------------------------------------------------------------
# handle_sigterm
# ---------------------------------------------------------------------------

def test_handle_sigterm_sets_shutdown_flag():
    ups_mqtt._shutdown = False
    ups_mqtt.handle_sigterm(None, None)
    assert ups_mqtt._shutdown is True
