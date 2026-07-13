import json
from unittest.mock import MagicMock, patch

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
