from __future__ import annotations

import subprocess

from ups_mqtt.domain.exceptions import NutUnavailable
from ups_mqtt.domain.models import BatteryMetrics, UpsReading
from ups_mqtt.ports.ups_port import IUpsPort

_BATTERY_FIELDS = (
    "battery.charge",
    "battery.charge.low",
    "battery.runtime",
    "battery.runtime.low",
    "battery.voltage",
    "battery.voltage.nominal",
)


class NutAdapter(IUpsPort):
    def __init__(self, ups_name: str, ups_host: str, ups_port: str) -> None:
        self._target = f"{ups_name}@{ups_host}:{ups_port}"

    def read(self) -> UpsReading:
        raw = self._run_upsc()
        return self._parse(raw)

    def _run_upsc(self) -> dict[str, str]:
        try:
            result = subprocess.run(
                ["upsc", self._target],
                capture_output=True,
                text=True,
            )
        except Exception as e:
            raise NutUnavailable(f"upsc subprocess failed: {e}") from e

        data: dict[str, str] = {}
        for line in result.stdout.splitlines():
            try:
                key, value = line.split(":", 1)
                data[key.strip()] = value.strip()
            except ValueError:
                pass
        return data

    @staticmethod
    def _parse(data: dict[str, str]) -> UpsReading:
        battery: BatteryMetrics | None
        try:
            battery = BatteryMetrics(
                charge=float(data["battery.charge"]),
                charge_low=float(data["battery.charge.low"]),
                runtime=float(data["battery.runtime"]),
                runtime_low=float(data["battery.runtime.low"]),
                voltage=float(data["battery.voltage"]),
                voltage_nominal=float(data["battery.voltage.nominal"]),
            )
        except (KeyError, ValueError):
            battery = None

        return UpsReading(
            status=data.get("ups.status", ""),
            load=_safe_float(data.get("ups.load", "0")),
            beeper_status=data.get("ups.beeper.status", ""),
            delay_shutdown=_safe_float(data.get("ups.delay.shutdown", "0")),
            battery=battery,
        )


def _safe_float(value: str) -> float:
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0
