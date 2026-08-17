from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from atlantis_core import build_availability_online, build_telemetry, effective_retain

if TYPE_CHECKING:
    from ups_mqtt.domain.models import UpsReading

logger = logging.getLogger("atlantis")


@dataclass(frozen=True)
class Topics:
    battery: str
    status: str
    availability: str          # this BRIDGE PROCESS's own availability (LWT-backed)
    ups_availability: str      # the bridged UPS's own availability (PLAT-244, mqtt.md D13)


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
        self._client.publish(
            self._topics.battery, payload, qos=0,
            retain=effective_retain(self._topics.battery),
        )
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
        self._client.publish(
            self._topics.status, payload, qos=0,
            retain=effective_retain(self._topics.status),
        )
        logger.info(f"Published UPS status: {payload}", extra={"subsystem": "mqtt"})

    def publish_ups_online(self, ts: str, ip: str, fw: str, mac: str) -> None:
        """Publish the bridged UPS's own availability as online (PLAT-244).

        NOT LWT-backed — the UPS has no MQTT connection of its own for an LWT
        to describe. This is an ordinary retained publish driven by the
        bridge's polling (mqtt.md D13), so it is called once per successful
        poll rather than once at connect time.
        """
        payload = build_availability_online(ts, ip=ip, fw=fw, mac=mac, spec="1.31")
        self._client.publish(
            self._topics.ups_availability, payload, qos=0,
            retain=effective_retain(self._topics.ups_availability),
        )
        logger.info(f"Published UPS availability: online ({payload})", extra={"subsystem": "mqtt"})

    def publish_ups_offline(self, ts: str) -> None:
        """Publish the bridged UPS's own availability as offline (PLAT-244).

        Called when NUT stops answering — the bridge is the only thing that
        can report this on the UPS's behalf, so it must do so explicitly
        rather than relying on an LWT (mqtt.md D13). Unlike the LWT payload
        (mqtt.md §3.2.2), this is an ordinary runtime publish, so it can and
        does carry a timestamp (§5.3.2 only forbids that for the LWT itself).
        """
        payload = json.dumps(
            {"status": "offline", "reason": "nut_unreachable", "timestamp": ts},
            separators=(",", ":"),
        )
        self._client.publish(
            self._topics.ups_availability, payload, qos=0,
            retain=effective_retain(self._topics.ups_availability),
        )
        logger.warning(f"Published UPS availability: offline (NUT unreachable)", extra={"subsystem": "mqtt"})
