import logging
from unittest.mock import MagicMock

import pytest

from ups_mqtt.application.ups_service import poll_and_publish, publish_ups_availability
from ups_mqtt.domain.exceptions import NutUnavailable
from ups_mqtt.domain.models import BatteryMetrics, UpsReading

TS = "2026-03-19T10:00:00Z"

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


@pytest.fixture
def logger():
    return logging.getLogger("test")


def test_poll_and_publish_returns_reading_on_success(logger):
    port = MagicMock()
    port.read.return_value = FULL_READING
    publisher = MagicMock()

    result = poll_and_publish(port, publisher, logger, TS)

    assert result is FULL_READING
    publisher.publish_battery.assert_called_once_with(FULL_READING, TS)
    publisher.publish_status.assert_called_once_with(FULL_READING, TS)


def test_poll_and_publish_returns_none_on_nut_unavailable(logger):
    port = MagicMock()
    port.read.side_effect = NutUnavailable("upsc not found")
    publisher = MagicMock()

    result = poll_and_publish(port, publisher, logger, TS)

    assert result is None
    publisher.publish_battery.assert_not_called()
    publisher.publish_status.assert_not_called()


def test_poll_and_publish_calls_both_publishers(logger):
    port = MagicMock()
    port.read.return_value = FULL_READING
    publisher = MagicMock()

    poll_and_publish(port, publisher, logger, TS)

    assert publisher.publish_battery.call_count == 1
    assert publisher.publish_status.call_count == 1


def test_poll_and_publish_reading_with_no_battery(logger):
    reading = UpsReading(status="OB", load=0.0, beeper_status="", delay_shutdown=0.0, battery=None)
    port = MagicMock()
    port.read.return_value = reading
    publisher = MagicMock()

    result = poll_and_publish(port, publisher, logger, TS)

    assert result is reading
    # Publisher is called; it decides internally whether to skip on battery=None
    publisher.publish_battery.assert_called_once_with(reading, TS)
    publisher.publish_status.assert_called_once_with(reading, TS)


# ---------------------------------------------------------------------------
# publish_ups_availability (PLAT-244) — the UPS's own availability, driven by
# each poll's outcome rather than by an MQTT connection (mqtt.md D13).
# ---------------------------------------------------------------------------

def test_publish_ups_availability_online_when_reading_present():
    publisher = MagicMock()
    publish_ups_availability(FULL_READING, publisher, TS, ip="192.168.1.50", fw_version="1.0.0", mac="c8c9a3d2f040")
    publisher.publish_ups_online.assert_called_once_with(TS, ip="192.168.1.50", fw="1.0.0", mac="c8c9a3d2f040")
    publisher.publish_ups_offline.assert_not_called()


def test_publish_ups_availability_offline_when_reading_is_none():
    # reading=None is exactly poll_and_publish's return value on NutUnavailable
    # (the offline-on-NUT-failure path) — this is the case D13 exists for.
    publisher = MagicMock()
    publish_ups_availability(None, publisher, TS, ip="192.168.1.50", fw_version="1.0.0", mac="c8c9a3d2f040")
    publisher.publish_ups_offline.assert_called_once_with(TS)
    publisher.publish_ups_online.assert_not_called()


def test_poll_and_publish_then_publish_ups_availability_offline_on_nut_failure(logger):
    # End-to-end of the offline path: a NutUnavailable failure in poll_and_publish
    # must translate into a UPS-availability offline publish, not a raised exception.
    port = MagicMock()
    port.read.side_effect = NutUnavailable("upsc not found")
    publisher = MagicMock()

    reading = poll_and_publish(port, publisher, logger, TS)
    publish_ups_availability(reading, publisher, TS, ip="192.168.1.50", fw_version="1.0.0", mac="c8c9a3d2f040")

    assert reading is None
    publisher.publish_ups_offline.assert_called_once_with(TS)
