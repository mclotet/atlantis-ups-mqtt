import json
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from atlantis_core import (
    AtlantisLogger,
    build,
    build_availability_offline,
    build_availability_online,
    build_availability_topic,
    build_telemetry,
    build_telemetry_topic,
)

# ---------------------------------------------------------------------------
# Configuration from environment
# ---------------------------------------------------------------------------

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))

SAMPLE_RATE_ONLINE = int(os.getenv("SAMPLE_RATE_ONLINE", 60))
SAMPLE_RATE_OFFLINE = int(os.getenv("SAMPLE_RATE_OFFLINE", 10))

UPS_NAME = os.getenv("UPS_NAME", "ups")
UPS_HOST = os.getenv("UPS_HOST", "localhost")
UPS_PORT = os.getenv("UPS_PORT", "3493")

ATL_GROUP_ID = os.getenv("ATL_GROUP_ID", "global")
ATL_EDGE_NODE_ID = os.getenv("ATL_EDGE_NODE_ID", "rack")
ATL_DEVICE_ID = os.getenv("ATL_DEVICE_ID", "raspberrypi5")
ATL_SERVICE_NAME = os.getenv("ATL_SERVICE_NAME", "ups-mqtt")
FW_VERSION = os.getenv("FW_VERSION", "1.0.0")

# ---------------------------------------------------------------------------
# MQTT topics
# ---------------------------------------------------------------------------

battery_topic = build_telemetry_topic(ATL_GROUP_ID, ATL_EDGE_NODE_ID, ATL_DEVICE_ID, "battery")
ups_status_topic = build(ATL_GROUP_ID, "state", ATL_EDGE_NODE_ID, ATL_DEVICE_ID, "ups", "status")
avail_topic = build_availability_topic(ATL_GROUP_ID, ATL_EDGE_NODE_ID, ATL_DEVICE_ID)

# ---------------------------------------------------------------------------
# State shared between callbacks and main loop
# ---------------------------------------------------------------------------

_connected = False
_shutdown = threading.Event()
_logger = None  # set after MQTT client is ready


# ---------------------------------------------------------------------------
# MQTT callbacks
# ---------------------------------------------------------------------------

def on_connect(client, userdata, flags, reason_code, properties):
    global _connected, _logger
    if reason_code == 0:
        _connected = True
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        birth = build_availability_online(ts)
        client.publish(avail_topic, birth, qos=1, retain=True)
        if _logger:
            _logger.info("Connected to MQTT broker", extra={"subsystem": "mqtt"})
    else:
        if _logger:
            _logger.error(f"MQTT connection refused: reason_code={reason_code}", extra={"subsystem": "mqtt"})


def on_disconnect(client, userdata, flags, reason_code, properties):
    global _connected
    _connected = False
    if _logger and not _shutdown.is_set():
        _logger.warning("Disconnected from MQTT broker", extra={"subsystem": "mqtt"})


# ---------------------------------------------------------------------------
# UPS data
# ---------------------------------------------------------------------------

def get_ups_data():
    try:
        result = subprocess.run(
            ["upsc", f"{UPS_NAME}@{UPS_HOST}:{UPS_PORT}"],
            capture_output=True,
            text=True,
        )
        ups = {}
        for line in result.stdout.splitlines():
            try:
                key, value = line.split(":", 1)
                ups[key.strip()] = value.strip()
            except ValueError:
                pass
        return ups
    except Exception as e:
        if _logger:
            _logger.error(f"Failed to run upsc: {e}", extra={"subsystem": "sensor"})
        return {}


def is_ups_online(ups_data):
    status = ups_data.get("ups.status", "")
    return "OL" in status


# ---------------------------------------------------------------------------
# Publish helpers
# ---------------------------------------------------------------------------

def publish_battery(client, ups_data, ts):
    try:
        values = {
            "charge":          float(ups_data["battery.charge"]),
            "charge_low":      float(ups_data["battery.charge.low"]),
            "runtime":         float(ups_data["battery.runtime"]),
            "runtime_low":     float(ups_data["battery.runtime.low"]),
            "voltage":         float(ups_data["battery.voltage"]),
            "voltage_nominal": float(ups_data["battery.voltage.nominal"]),
        }
        payload = build_telemetry(values, ts)
        client.publish(battery_topic, payload, qos=0, retain=False)
        if _logger:
            _logger.info(f"Published battery telemetry: {payload}", extra={"subsystem": "mqtt"})
    except (KeyError, ValueError) as e:
        if _logger:
            _logger.warning(f"Battery field missing or invalid: {e}", extra={"subsystem": "sensor"})


def publish_ups_status(client, ups_data, ts):
    try:
        state = {
            "status":         ups_data.get("ups.status", ""),
            "load":           float(ups_data.get("ups.load", 0)),
            "beeper_status":  ups_data.get("ups.beeper.status", ""),
            "delay_shutdown": float(ups_data.get("ups.delay.shutdown", 0)),
            "timestamp":      ts,
        }
        payload = json.dumps(state)
        client.publish(ups_status_topic, payload, qos=1, retain=True)
        if _logger:
            _logger.info(f"Published UPS status: {payload}", extra={"subsystem": "mqtt"})
    except (KeyError, ValueError) as e:
        if _logger:
            _logger.warning(f"UPS status field missing or invalid: {e}", extra={"subsystem": "sensor"})


# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------

def handle_sigterm(signum, frame):
    _shutdown.set()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global _connected, _logger

    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, handle_sigterm)

    # Build MQTT client with LWT registered before connect
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.will_set(avail_topic, build_availability_offline(), qos=1, retain=True)

    # Configure logger (stdout only until broker is connected)
    _logger = AtlantisLogger.configure(
        service_name=ATL_SERVICE_NAME,
        device_id=ATL_DEVICE_ID,
        group_id=ATL_GROUP_ID,
    )
    _logger.info("Starting UPS to MQTT bridge", extra={"subsystem": "boot"})

    # Initial broker connection with retry
    backoff = 1
    while not _shutdown.is_set():
        try:
            _logger.info(f"Connecting to MQTT broker at {MQTT_HOST}:{MQTT_PORT}", extra={"subsystem": "mqtt"})
            client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            client.loop_start()

            # Re-configure logger with MQTT handler now that client is available
            _logger = AtlantisLogger.configure(
                service_name=ATL_SERVICE_NAME,
                device_id=ATL_DEVICE_ID,
                group_id=ATL_GROUP_ID,
                mqtt_client=client,
            )
            break
        except Exception as e:
            _logger.error(f"Could not connect to broker: {e} — retrying in {backoff}s", extra={"subsystem": "mqtt"})
            _shutdown.wait(backoff)
            backoff = min(backoff * 2, 60)

    if _shutdown.is_set():
        sys.exit(0)

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

        ups_data = get_ups_data()
        if not ups_data:
            _logger.warning("No UPS data available, retrying...", extra={"subsystem": "sensor"})
            _shutdown.wait(SAMPLE_RATE_OFFLINE)
            continue

        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        publish_battery(client, ups_data, ts)
        publish_ups_status(client, ups_data, ts)

        sample_rate = SAMPLE_RATE_ONLINE if is_ups_online(ups_data) else SAMPLE_RATE_OFFLINE
        _shutdown.wait(sample_rate)

    # Graceful shutdown sequence
    _logger.info("Shutting down gracefully", extra={"subsystem": "shutdown"})
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    offline_payload = json.dumps({
        "status": "offline",
        "reason": "graceful_shutdown",
        "timestamp": ts,
    })
    client.publish(avail_topic, offline_payload, qos=1, retain=True)
    time.sleep(0.5)  # allow broker to receive before disconnect
    client.loop_stop()
    client.disconnect()
    _logger.info("Service stopped", extra={"subsystem": "shutdown"})


if __name__ == "__main__":
    main()
