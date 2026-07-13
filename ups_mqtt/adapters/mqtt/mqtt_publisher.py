from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from atlantis_core import build_telemetry

if TYPE_CHECKING:
    from ups_mqtt.domain.models import UpsReading

logger = logging.getLogger("atlantis")


@dataclass(frozen=True)
class Topics:
    battery: str
    status: str
    availability: str


class MqttPublisher:
    def __init__(self, client: object, topics: Topics) -> None:
        self._client = client
        self._topics = topics

    def publish_battery(self, reading: UpsReading, ts: str) -> None:
        if reading.battery is None:
            logger.warning("Battery metrics unavailable, skipping publish", extra={"subsystem": "sensor"})
            return
        b = reading.battery
        values = {
            "charge":          b.charge,
            "charge_low":      b.charge_low,
            "runtime":         b.runtime,
            "runtime_low":     b.runtime_low,
            "voltage":         b.voltage,
            "voltage_nominal": b.voltage_nominal,
        }
        payload = build_telemetry(values, ts)
        self._client.publish(self._topics.battery, payload, qos=0, retain=False)
        logger.info(f"Published battery telemetry: {payload}", extra={"subsystem": "mqtt"})

    def publish_status(self, reading: UpsReading, ts: str) -> None:
        state = {
            "status":         reading.status,
            "load":           reading.load,
            "beeper_status":  reading.beeper_status,
            "delay_shutdown": reading.delay_shutdown,
            "timestamp":      ts,
        }
        payload = json.dumps(state)
        self._client.publish(self._topics.status, payload, qos=0, retain=True)
        logger.info(f"Published UPS status: {payload}", extra={"subsystem": "mqtt"})
