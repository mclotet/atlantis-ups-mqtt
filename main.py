import signal
import socket
import sys
import threading
import time
import uuid
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from atlantis_core import (
    AtlantisLogger,
    build,
    build_availability_offline,
    build_availability_online,
    build_availability_topic,
    build_telemetry_topic,
)

from ups_mqtt.adapters.mqtt.mqtt_publisher import MqttPublisher, Topics
from ups_mqtt.adapters.nut.nut_adapter import NutAdapter
from ups_mqtt.application.ups_service import poll_and_publish
from ups_mqtt.config import get_settings

# ---------------------------------------------------------------------------
# State shared between callbacks and main loop
# ---------------------------------------------------------------------------

_connected = False
_shutdown = threading.Event()
_logger = None  # set in main() after MQTT client is ready


# ---------------------------------------------------------------------------
# Network helpers
# ---------------------------------------------------------------------------

def _get_network_info() -> tuple[str, str]:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = "0.0.0.0"
    mac = hex(uuid.getnode())[2:].zfill(12)
    return ip, mac


# ---------------------------------------------------------------------------
# MQTT callbacks
# ---------------------------------------------------------------------------

def _make_on_connect(avail_topic: str, fw_version: str):
    def on_connect(client, userdata, flags, reason_code, properties):
        global _connected
        if reason_code == 0:
            _connected = True
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            ip, mac = _get_network_info()
            birth = build_availability_online(ts, ip=ip, fw=fw_version, mac=mac, spec="1.18")
            client.publish(avail_topic, birth, qos=1, retain=True)
            if _logger:
                _logger.info("Connected to MQTT broker", extra={"subsystem": "mqtt"})
        else:
            if _logger:
                _logger.error(
                    f"MQTT connection refused: reason_code={reason_code}",
                    extra={"subsystem": "mqtt"},
                )
    return on_connect


def _make_on_disconnect():
    def on_disconnect(client, userdata, flags, reason_code, properties):
        global _connected
        _connected = False
        if _logger and not _shutdown.is_set():
            _logger.warning("Disconnected from MQTT broker", extra={"subsystem": "mqtt"})
    return on_disconnect


# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------

def _handle_sigterm(signum, frame):
    _shutdown.set()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    global _connected, _logger

    signal.signal(signal.SIGTERM, _handle_sigterm)
    signal.signal(signal.SIGINT, _handle_sigterm)

    settings = get_settings()

    group = settings.atl_group_id
    edge_node = settings.atl_edge_node_id
    device = settings.atl_device_id
    fw_version = settings.fw_version

    # Pre-build topics
    topics = Topics(
        battery=build_telemetry_topic(group, edge_node, device, "battery"),
        status=build(group, "state", edge_node, device, "ups", "status"),
        availability=build_availability_topic(group, edge_node, device),
    )

    avail_topic = topics.availability

    # Bootstrap logger — stdout only until broker is connected
    _logger = AtlantisLogger.configure(
        service_name=settings.atl_service_name,
        device_id=device,
        group_id=group,
    )
    _logger.info("Starting UPS to MQTT bridge", extra={"subsystem": "boot"})

    # Build MQTT client with LWT
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = _make_on_connect(avail_topic, fw_version)
    client.on_disconnect = _make_on_disconnect()
    client.will_set(avail_topic, build_availability_offline(), qos=1, retain=True)

    # Initial broker connection with exponential backoff
    backoff = 1
    while not _shutdown.is_set():
        try:
            _logger.info(
                f"Connecting to MQTT broker at {settings.mqtt_host}:{settings.mqtt_port}",
                extra={"subsystem": "mqtt"},
            )
            client.connect(settings.mqtt_host, settings.mqtt_port, keepalive=60)
            client.loop_start()
            # Re-configure logger with MQTT handler now that client is available
            _logger = AtlantisLogger.configure(
                service_name=settings.atl_service_name,
                device_id=device,
                group_id=group,
                mqtt_client=client,
            )
            break
        except Exception as e:
            _logger.error(
                f"Could not connect to broker: {e} — retrying in {backoff}s",
                extra={"subsystem": "mqtt"},
            )
            _shutdown.wait(backoff)
            backoff = min(backoff * 2, 60)

    if _shutdown.is_set():
        sys.exit(0)

    # Instantiate adapters
    port = NutAdapter(settings.ups_name, settings.ups_host, settings.ups_port)
    publisher = MqttPublisher(client, topics)

    # Main loop
    backoff = 1
    while not _shutdown.is_set():
        if not _connected:
            _logger.warning(f"Broker disconnected, reconnecting in {backoff}s", extra={"subsystem": "mqtt"})
            _shutdown.wait(backoff)
            backoff = min(backoff * 2, 60)
            try:
                client.reconnect()
            except Exception as e:
                _logger.error(f"Reconnect failed: {e}", extra={"subsystem": "mqtt"})
            continue

        backoff = 1  # reset on successful connection

        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        reading = poll_and_publish(port, publisher, _logger, ts)

        if reading is None:
            _shutdown.wait(settings.sample_rate_offline)
        else:
            sample_rate = settings.sample_rate_online if reading.is_online() else settings.sample_rate_offline
            _shutdown.wait(sample_rate)

    # Graceful shutdown
    _logger.info("Shutting down gracefully", extra={"subsystem": "shutdown"})
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    import json
    offline_payload = json.dumps({"status": "offline", "reason": "graceful_shutdown", "timestamp": ts})
    client.publish(avail_topic, offline_payload, qos=1, retain=True)
    time.sleep(0.5)
    client.loop_stop()
    client.disconnect()
    _logger.info("Service stopped", extra={"subsystem": "shutdown"})


if __name__ == "__main__":
    main()
