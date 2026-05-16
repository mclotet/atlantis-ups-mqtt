from unittest.mock import MagicMock, patch

import pytest

from ups_mqtt.adapters.nut.nut_adapter import NutAdapter
from ups_mqtt.domain.exceptions import NutUnavailable


def _make_upsc_result(stdout: str) -> MagicMock:
    result = MagicMock()
    result.stdout = stdout
    return result


FULL_OUTPUT = (
    "battery.charge: 100\n"
    "battery.charge.low: 10\n"
    "battery.runtime: 2340\n"
    "battery.runtime.low: 120\n"
    "battery.voltage: 27.2\n"
    "battery.voltage.nominal: 24.0\n"
    "ups.status: OL\n"
    "ups.load: 18.5\n"
    "ups.beeper.status: enabled\n"
    "ups.delay.shutdown: 20\n"
)

ADAPTER = NutAdapter("ups", "localhost", "3493")


def test_read_parses_ups_status():
    with patch("subprocess.run", return_value=_make_upsc_result(FULL_OUTPUT)):
        reading = ADAPTER.read()
    assert reading.status == "OL"


def test_read_parses_load():
    with patch("subprocess.run", return_value=_make_upsc_result(FULL_OUTPUT)):
        reading = ADAPTER.read()
    assert reading.load == 18.5


def test_read_parses_battery_metrics():
    with patch("subprocess.run", return_value=_make_upsc_result(FULL_OUTPUT)):
        reading = ADAPTER.read()
    assert reading.battery is not None
    assert reading.battery.charge == 100.0
    assert reading.battery.charge_low == 10.0
    assert reading.battery.runtime == 2340.0
    assert reading.battery.runtime_low == 120.0
    assert reading.battery.voltage == 27.2
    assert reading.battery.voltage_nominal == 24.0


def test_read_strips_whitespace():
    output = "ups.status:  OL  \nbattery.charge:  99  \n"
    with patch("subprocess.run", return_value=_make_upsc_result(output)):
        reading = ADAPTER.read()
    assert reading.status == "OL"


def test_read_skips_malformed_lines():
    output = "this line has no colon\nups.status: OL\n"
    with patch("subprocess.run", return_value=_make_upsc_result(output)):
        reading = ADAPTER.read()
    assert reading.status == "OL"


def test_read_value_with_colon():
    output = "driver.version: 2.8.1-5 (NUT v2.8.1)\nups.status: OL\n"
    with patch("subprocess.run", return_value=_make_upsc_result(output)):
        reading = ADAPTER.read()
    assert reading.status == "OL"


def test_read_raises_nut_unavailable_on_subprocess_exception():
    with patch("subprocess.run", side_effect=OSError("upsc not found")):
        with pytest.raises(NutUnavailable):
            ADAPTER.read()


def test_read_returns_none_battery_on_missing_fields():
    output = "ups.status: OB\nups.load: 5\n"  # no battery fields
    with patch("subprocess.run", return_value=_make_upsc_result(output)):
        reading = ADAPTER.read()
    assert reading.battery is None


def test_read_returns_none_battery_on_invalid_float():
    bad_output = FULL_OUTPUT.replace("battery.charge: 100", "battery.charge: not-a-number")
    with patch("subprocess.run", return_value=_make_upsc_result(bad_output)):
        reading = ADAPTER.read()
    assert reading.battery is None


def test_read_empty_output_returns_empty_status():
    with patch("subprocess.run", return_value=_make_upsc_result("")):
        reading = ADAPTER.read()
    assert reading.status == ""
    assert reading.battery is None


def test_read_is_online_true_for_ol():
    with patch("subprocess.run", return_value=_make_upsc_result(FULL_OUTPUT)):
        reading = ADAPTER.read()
    assert reading.is_online() is True


def test_read_is_online_false_for_ob():
    output = FULL_OUTPUT.replace("ups.status: OL", "ups.status: OB")
    with patch("subprocess.run", return_value=_make_upsc_result(output)):
        reading = ADAPTER.read()
    assert reading.is_online() is False
