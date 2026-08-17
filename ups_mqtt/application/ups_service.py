from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ups_mqtt.domain.exceptions import UpsDomainError

if TYPE_CHECKING:
    from ups_mqtt.domain.models import UpsReading
    from ups_mqtt.ports.ups_port import IUpsPort


def poll_and_publish(
    port: IUpsPort,
    publisher: object,
    logger: logging.Logger,
    ts: str,
) -> UpsReading | None:
    """Read UPS data via port and publish via publisher.

    Returns the UpsReading on success (caller uses it for sample-rate decision),
    or None if the port raises a domain error.
    """
    try:
        reading = port.read()
    except UpsDomainError as e:
        logger.warning(str(e), extra={"subsystem": "sensor"})
        return None
    publisher.publish_battery(reading, ts)
    publisher.publish_status(reading, ts)
    return reading


def publish_ups_availability(
    reading: UpsReading | None,
    publisher: object,
    ts: str,
    ip: str,
    fw_version: str,
    mac: str,
) -> None:
    """Publish the bridged UPS's own availability topic (identity.md §2.2, PLAT-244).

    Unlike the bridge PROCESS's own availability (LWT-backed — mqtt.md
    §3.2.2), this topic has no MQTT connection to describe: it reports NUT
    reachability instead, so it is an ordinary retained publish driven by
    each poll cycle (mqtt.md D13) rather than a connect-time birth message.
    Called every cycle — including on failure — so the retained topic
    self-heals the same way `state` topics do (mqtt.md §5.1): the bridge
    must explicitly publish offline when NUT stops answering, since nothing
    else can.

    `reading` is `poll_and_publish`'s return value: `None` means the most
    recent `port.read()` raised `UpsDomainError` (NUT unreachable).
    """
    if reading is None:
        publisher.publish_ups_offline(ts)
    else:
        publisher.publish_ups_online(ts, ip=ip, fw=fw_version, mac=mac)
