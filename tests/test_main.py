import json
import logging
from unittest.mock import MagicMock, patch

import paho.mqtt.client as mqtt

import main
from main import _make_on_connect

AVAIL_TOPIC = "atlantis/global/availability/rack/raspberrypi5/node/status"
FW_VERSION = "1.0.0"


def test_on_connect_publishes_birth_at_qos_0_retained():
    client = MagicMock()
    mock_sock = MagicMock()
    mock_sock.getsockname.return_value = ("192.168.1.1", 0)
    on_connect = _make_on_connect(AVAIL_TOPIC, FW_VERSION)

    with patch("main.socket.socket", return_value=mock_sock):
        on_connect(client, None, None, 0, None)

    client.publish.assert_called_once()
    call_args = client.publish.call_args
    assert call_args[0][0] == AVAIL_TOPIC
    payload = json.loads(call_args[0][1])
    assert payload["status"] == "online"
    assert call_args[1]["qos"] == 0
    assert call_args[1]["retain"] is True


def test_on_connect_refused_does_not_publish():
    client = MagicMock()
    on_connect = _make_on_connect(AVAIL_TOPIC, FW_VERSION)
    on_connect(client, None, None, 5, None)
    client.publish.assert_not_called()


# ---------------------------------------------------------------------------
# Birth publish result is checked, not assumed (PLAT-257)
# ---------------------------------------------------------------------------

def test_on_connect_logs_error_when_birth_publish_does_not_reach_broker():
    client = MagicMock()
    info = MagicMock()
    info.rc = mqtt.MQTT_ERR_NO_CONN
    client.publish.return_value = info
    mock_sock = MagicMock()
    mock_sock.getsockname.return_value = ("192.168.1.1", 0)

    fake_logger = MagicMock()
    on_connect = _make_on_connect(AVAIL_TOPIC, FW_VERSION)

    with patch("main.socket.socket", return_value=mock_sock), patch.object(main, "_logger", fake_logger):
        on_connect(client, None, None, 0, None)

    assert fake_logger.error.called, "a birth publish that never reached the broker must not be logged as 'Connected'"
    assert not fake_logger.info.called


def test_on_connect_logs_connected_when_birth_publish_reaches_broker():
    client = MagicMock()
    info = MagicMock()
    info.rc = mqtt.MQTT_ERR_SUCCESS
    client.publish.return_value = info
    mock_sock = MagicMock()
    mock_sock.getsockname.return_value = ("192.168.1.1", 0)

    fake_logger = MagicMock()
    on_connect = _make_on_connect(AVAIL_TOPIC, FW_VERSION)

    with patch("main.socket.socket", return_value=mock_sock), patch.object(main, "_logger", fake_logger):
        on_connect(client, None, None, 0, None)

    assert fake_logger.info.called
    assert not fake_logger.error.called


# ---------------------------------------------------------------------------
# No redundant manual reconnect() (PLAT-257)
#
# loop_start() already runs loop_forever(), which retries a dropped connection
# itself (reconnect_on_failure=True is the paho default). Calling
# client.reconnect() again from the main loop races that background thread on
# the same Client's unsynchronized socket/queue state (reconnect() replaces
# self._sock and clears self._out_packet with no lock) and can leave a qos=0
# publish silently written to a socket the network thread already superseded —
# exactly the "stale client handle" failure mode this ticket was filed for.
# ---------------------------------------------------------------------------

def test_main_does_not_call_reconnect_itself():
    import inspect
    source = inspect.getsource(main.main)
    code_lines = [line for line in source.splitlines() if not line.strip().startswith("#")]
    assert not any("reconnect(" in line for line in code_lines), (
        "main() must not call client.reconnect() itself — paho's own loop_forever() "
        "(started via loop_start()) already retries a dropped connection; a second, "
        "concurrent manual reconnect() races it on unsynchronized Client state"
    )
