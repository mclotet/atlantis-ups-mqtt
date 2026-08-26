"""End-to-end regression test for PLAT-257 against a real local broker.

The bug: ups-mqtt's own availability publish appeared to succeed in the logs
every poll cycle, but nothing after the very first (container-boot) message
ever reached the broker. Root causes fixed alongside this test:

  1. main.py's main loop called client.reconnect() itself whenever it saw the
     client disconnected. But client.loop_start() already runs
     loop_forever(), which retries a dropped connection on its own
     (reconnect_on_failure=True is paho's default) — see paho.mqtt.client's
     own loop_forever() source. A second, concurrent manual reconnect() call
     races that background thread on the same Client's unsynchronized
     _sock/_out_packet state (reconnect() clears/replaces both without a
     lock), and can leave publishes silently written to a socket the network
     thread already superseded.
  2. Every publish call site discarded client.publish()'s return value, so a
     publish that failed (qos=0 returns MQTT_ERR_NO_CONN synchronously when
     not connected — it is not queued) was logged as a success regardless.

This test runs a real local aMQTT broker, drops the publisher's TCP
connection out from under it (simulating a real network blip rather than a
clean disconnect() call, which paho treats differently), and asserts that
MqttPublisher.publish_ups_online keeps landing on the broker afterwards —
observed by a second, independent subscriber client — without the
application ever calling reconnect() itself.
"""

from __future__ import annotations

import asyncio
import json
import socket
import threading
import time

import paho.mqtt.client as mqtt
import pytest

amqtt_broker = pytest.importorskip("amqtt.broker", reason="amqtt not installed; skipping live-broker PLAT-257 regression test")

from ups_mqtt.adapters.mqtt.mqtt_publisher import MqttPublisher, Topics  # noqa: E402

UPS_AVAILABILITY_TOPIC = "atlantis/global/availability/power/apc-smartups750/node/status"

TOPICS = Topics(
    battery="atlantis/global/data/power/apc-smartups750/battery/telemetry",
    status="atlantis/global/state/power/apc-smartups750/ups/status",
    availability="atlantis/global/availability/infra/ups-mqtt/node/status",
    ups_availability=UPS_AVAILABILITY_TOPIC,
)


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _LocalBroker:
    """A real MQTT broker (amqtt) running in a background thread/event loop."""

    def __init__(self) -> None:
        self.port = _free_port()
        self._ready = threading.Event()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        async def _main():
            broker = amqtt_broker.Broker({
                "listeners": {"default": {"type": "tcp", "bind": f"127.0.0.1:{self.port}"}},
                "plugins": {
                    "amqtt.plugins.authentication.AnonymousAuthPlugin": {"allow_anonymous": True},
                },
            })
            await broker.start()
            self._ready.set()
            while not self._stop.is_set():
                await asyncio.sleep(0.05)
            await broker.shutdown()

        asyncio.run(_main())

    def start(self) -> None:
        self._thread.start()
        assert self._ready.wait(timeout=5), "local test broker failed to start"

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)


@pytest.fixture
def broker():
    b = _LocalBroker()
    b.start()
    yield b
    b.stop()


def test_ups_availability_publishes_survive_a_dropped_connection(broker):
    received: list[str] = []

    def on_message(client, userdata, msg):
        received.append(msg.payload.decode())

    subscriber = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    subscriber.on_message = on_message
    subscriber.connect("127.0.0.1", broker.port)
    subscriber.subscribe(UPS_AVAILABILITY_TOPIC)
    subscriber.loop_start()

    connected = threading.Event()

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            connected.set()

    def on_disconnect(client, userdata, flags, reason_code, properties):
        connected.clear()

    publisher_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    publisher_client.on_connect = on_connect
    publisher_client.on_disconnect = on_disconnect
    publisher_client.connect("127.0.0.1", broker.port, keepalive=60)
    publisher_client.loop_start()
    assert connected.wait(timeout=5), "publisher never connected to the local broker"

    publisher = MqttPublisher(publisher_client, TOPICS)

    # Cycle 1: publish while healthy — must reach the subscriber.
    publisher.publish_ups_online("2026-08-26T10:00:00Z", ip="192.168.1.50", fw="1.0.0", mac="c8c9a3d2f040")
    time.sleep(0.5)
    assert len(received) == 1
    assert json.loads(received[0])["timestamp"] == "2026-08-26T10:00:00Z"

    # Simulate a real network blip: yank the socket out from under paho rather
    # than calling disconnect() (which is a *clean* shutdown paho does not
    # auto-reconnect from). This is what a flaky link or a broker restart
    # looks like from the client's side.
    connected.clear()
    publisher_client.socket().close()
    assert connected.wait(timeout=10), (
        "paho's own loop_forever() (via loop_start()) did not reconnect on its own — "
        "if this fails, something regressed the assumption this fix depends on"
    )

    # Cycle 2, post-reconnect: this is the exact symptom from the ticket — the
    # only message ever produced was the boot-time one, and this call is what
    # should now succeed after the reconnect instead of updating a client the
    # background thread has already replaced.
    publisher.publish_ups_online("2026-08-26T10:01:00Z", ip="192.168.1.50", fw="1.0.0", mac="c8c9a3d2f040")
    time.sleep(0.5)
    assert len(received) == 2, "the post-reconnect availability publish never reached the broker"
    assert json.loads(received[1])["timestamp"] == "2026-08-26T10:01:00Z"

    # A third cycle to rule out a one-off: the topic must keep updating, not
    # freeze again after a single post-reconnect message.
    publisher.publish_ups_online("2026-08-26T10:02:00Z", ip="192.168.1.50", fw="1.0.0", mac="c8c9a3d2f040")
    time.sleep(0.5)
    assert len(received) == 3
    assert json.loads(received[2])["timestamp"] == "2026-08-26T10:02:00Z"

    publisher_client.loop_stop()
    subscriber.loop_stop()


def test_publish_while_genuinely_disconnected_reports_failure_not_success(broker, caplog):
    import logging

    connected = threading.Event()

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            connected.set()

    publisher_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    publisher_client.on_connect = on_connect
    publisher_client.connect("127.0.0.1", broker.port, keepalive=60)
    publisher_client.loop_start()
    assert connected.wait(timeout=5)

    publisher = MqttPublisher(publisher_client, TOPICS)

    # Close the socket and publish immediately, before the background thread's
    # own auto-reconnect has a chance to complete — this is the exact window
    # in which qos=0 publish() returns MQTT_ERR_NO_CONN without raising.
    publisher_client.socket().close()

    with caplog.at_level(logging.ERROR, logger="atlantis"):
        publisher.publish_ups_online("2026-08-26T10:00:00Z", ip="192.168.1.50", fw="1.0.0", mac="c8c9a3d2f040")

    assert any(r.levelno >= logging.ERROR for r in caplog.records), (
        "a publish that never reached the broker must not be logged as success"
    )

    publisher_client.loop_stop()
