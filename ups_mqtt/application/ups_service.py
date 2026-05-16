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
