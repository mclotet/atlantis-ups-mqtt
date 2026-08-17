import json
from unittest.mock import MagicMock

import pytest

from ups_mqtt.adapters.mqtt.mqtt_publisher import MqttPublisher, Topics
from ups_mqtt.domain.models import BatteryMetrics, UpsReading

TS = "2026-03-19T10:00:00Z"

TOPICS = Topics(
    battery="atlantis/global/data/power/apc-smartups750/battery/telemetry",
    status="atlantis/global/state/power/apc-smartups750/ups/status",
    availability="atlantis/global/availability/infra/ups-mqtt/node/status",
    ups_availability="atlantis/global/availability/power/apc-smartups750/node/status",
)

FULL_READING = UpsReading(
    status="OL",
    load=18.5,
    beeper_status="enabled",
    delay_shutdown=20.0,
    battery=BatteryMetrics(
        charge=100.0,
        charge_low=10.0,
        runtime=2340.0,
        runtime_low=120.0,
        voltage=27.2,
        voltage_nominal=24.0,
    ),
)

READING_NO_BATTERY = UpsReading(
    status="OB",
    load=5.0,
    beeper_status="",
    delay_shutdown=0.0,
    battery=None,
)


# ---------------------------------------------------------------------------
# publish_battery
# ---------------------------------------------------------------------------

def test_publish_battery_publishes_to_correct_topic():
    client = MagicMock()
    pub = MqttPublisher(client, TOPICS)
    pub.publish_battery(FULL_READING, TS)
    topic = client.publish.call_args[0][0]
    assert topic == TOPICS.battery


def test_publish_battery_payload_is_valid_json():
    client = MagicMock()
    pub = MqttPublisher(client, TOPICS)
    pub.publish_battery(FULL_READING, TS)
    payload_str = client.publish.call_args[0][1]
    data = json.loads(payload_str)
    assert isinstance(data, dict)


def test_publish_battery_payload_contains_all_fields():
    client = MagicMock()
    pub = MqttPublisher(client, TOPICS)
    pub.publish_battery(FULL_READING, TS)
    payload = json.loads(client.publish.call_args[0][1])
    assert payload["charge"]          == 100.0
    assert payload["charge_low"]      == 10.0
    assert payload["runtime"]         == 2340.0
    assert payload["runtime_low"]     == 120.0
    assert payload["voltage"]         == 27.2
    assert payload["voltage_nominal"] == 24.0
    assert payload["timestamp"]       == TS


def test_publish_battery_uses_qos_0_no_retain():
    client = MagicMock()
    pub = MqttPublisher(client, TOPICS)
    pub.publish_battery(FULL_READING, TS)
    kwargs = client.publish.call_args[1]
    assert kwargs["qos"]    == 0
    assert kwargs["retain"] is False


def test_publish_battery_skips_when_battery_is_none():
    client = MagicMock()
    pub = MqttPublisher(client, TOPICS)
    pub.publish_battery(READING_NO_BATTERY, TS)
    client.publish.assert_not_called()


# ---------------------------------------------------------------------------
# publish_status
# ---------------------------------------------------------------------------

def test_publish_status_publishes_to_correct_topic():
    client = MagicMock()
    pub = MqttPublisher(client, TOPICS)
    pub.publish_status(FULL_READING, TS)
    topic = client.publish.call_args[0][0]
    assert topic == TOPICS.status


def test_publish_status_payload_is_valid_json():
    client = MagicMock()
    pub = MqttPublisher(client, TOPICS)
    pub.publish_status(FULL_READING, TS)
    data = json.loads(client.publish.call_args[0][1])
    assert isinstance(data, dict)


def test_publish_status_payload_contains_all_fields():
    client = MagicMock()
    pub = MqttPublisher(client, TOPICS)
    pub.publish_status(FULL_READING, TS)
    data = json.loads(client.publish.call_args[0][1])
    assert data["status"]         == "OL"
    assert data["load"]           == 18.5
    assert data["beeper_status"]  == "enabled"
    assert data["delay_shutdown"] == 20.0
    assert data["timestamp"]      == TS


def test_publish_status_uses_qos_0_retain():
    client = MagicMock()
    pub = MqttPublisher(client, TOPICS)
    pub.publish_status(FULL_READING, TS)
    kwargs = client.publish.call_args[1]
    assert kwargs["qos"]    == 0
    assert kwargs["retain"] is True


def test_publish_status_works_with_no_battery():
    client = MagicMock()
    pub = MqttPublisher(client, TOPICS)
    pub.publish_status(READING_NO_BATTERY, TS)
    data = json.loads(client.publish.call_args[0][1])
    assert data["status"] == "OB"
    assert data["load"]   == 5.0


# ---------------------------------------------------------------------------
# publish_ups_online / publish_ups_offline (PLAT-244)
# ---------------------------------------------------------------------------

def test_publish_ups_online_publishes_to_ups_availability_topic():
    client = MagicMock()
    pub = MqttPublisher(client, TOPICS)
    pub.publish_ups_online(TS, ip="192.168.1.50", fw="1.0.0", mac="c8c9a3d2f040")
    topic = client.publish.call_args[0][0]
    assert topic == TOPICS.ups_availability


def test_publish_ups_online_payload_shape():
    client = MagicMock()
    pub = MqttPublisher(client, TOPICS)
    pub.publish_ups_online(TS, ip="192.168.1.50", fw="1.0.0", mac="c8c9a3d2f040")
    payload = json.loads(client.publish.call_args[0][1])
    assert payload["status"]    == "online"
    assert payload["timestamp"] == TS
    assert payload["ip"]        == "192.168.1.50"
    assert payload["fw"]        == "1.0.0"
    assert payload["mac"]       == "c8c9a3d2f040"


def test_publish_ups_online_uses_qos_0_retained():
    client = MagicMock()
    pub = MqttPublisher(client, TOPICS)
    pub.publish_ups_online(TS, ip="192.168.1.50", fw="1.0.0", mac="c8c9a3d2f040")
    kwargs = client.publish.call_args[1]
    assert kwargs["qos"]    == 0
    assert kwargs["retain"] is True


def test_publish_ups_offline_publishes_to_ups_availability_topic():
    client = MagicMock()
    pub = MqttPublisher(client, TOPICS)
    pub.publish_ups_offline(TS)
    topic = client.publish.call_args[0][0]
    assert topic == TOPICS.ups_availability


def test_publish_ups_offline_payload_shape_and_reason():
    client = MagicMock()
    pub = MqttPublisher(client, TOPICS)
    pub.publish_ups_offline(TS)
    payload = json.loads(client.publish.call_args[0][1])
    assert payload["status"]    == "offline"
    assert payload["reason"]    == "nut_unreachable"
    assert payload["timestamp"] == TS


def test_publish_ups_offline_uses_qos_0_retained():
    client = MagicMock()
    pub = MqttPublisher(client, TOPICS)
    pub.publish_ups_offline(TS)
    kwargs = client.publish.call_args[1]
    assert kwargs["qos"]    == 0
    assert kwargs["retain"] is True


def test_ups_availability_topic_distinct_from_bridge_availability_topic():
    # Regression guard for the PLAT-244 split: the UPS's own availability
    # topic must never collapse onto the bridge process's availability topic.
    assert TOPICS.ups_availability != TOPICS.availability
