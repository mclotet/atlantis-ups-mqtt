"""PLAT-197: main.build_client applies ATL_MQTT_USERNAME / ATL_MQTT_PASSWORD.

A fake client stands in for paho: no broker, no network.
"""

import pytest

import main
from atlantis_core.mqtt_auth import MqttAuthConfigError
from ups_mqtt.config import Settings

AVAIL = "atlantis/global/availability/infra/ups-mqtt/node/status"


class FakeClient:
    def __init__(self):
        self.auth = []
        self.will = None

    def username_pw_set(self, username, password=None):
        self.auth.append((username, password))

    def will_set(self, topic, payload, qos=0, retain=False):
        self.will = (topic, qos, retain)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MQTT_HOST", "mqtt")
    monkeypatch.setenv("UPS_HOST", "nut-upsd")
    monkeypatch.setenv("UPS_NAME", "ups")
    monkeypatch.setenv("UPS_DEVICE_ID", "apc-smartups750")
    for key in ("ATL_MQTT_USERNAME", "ATL_MQTT_PASSWORD"):
        monkeypatch.delenv(key, raising=False)
    return monkeypatch


def _build(fake):
    return main.build_client(Settings(), AVAIL, "1.0.0", client_factory=lambda: fake)


def test_unset_username_stays_anonymous(env):
    fake = FakeClient()
    assert _build(fake) is fake
    assert fake.auth == []
    assert fake.will[0] == AVAIL


def test_credentials_applied(env):
    env.setenv("ATL_MQTT_USERNAME", "ups-mqtt")
    env.setenv("ATL_MQTT_PASSWORD", "pw0123456789")
    fake = FakeClient()
    _build(fake)
    assert fake.auth == [("ups-mqtt", "pw0123456789")]
    assert fake.will[0] == AVAIL


def test_username_without_password_fails_at_startup(env):
    env.setenv("ATL_MQTT_USERNAME", "ups-mqtt")
    with pytest.raises(MqttAuthConfigError):
        _build(FakeClient())
