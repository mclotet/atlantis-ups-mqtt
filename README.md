# atlantis-ups-mqtt

Polls a NUT (Network UPS Tools) daemon and publishes UPS telemetry to an MQTT broker.

The standalone `docker-compose.yml` includes both `nut-upsd` and `ups-mqtt` since they are tightly coupled — `nut-upsd` talks to the UPS over USB and exposes a NUT server; `ups-mqtt` queries it and forwards metrics to MQTT.

## Standalone usage

Requires a physical UPS connected via USB and an MQTT broker reachable at `MQTT_HOST`.

```bash
cp .env.example .env
# Edit .env: set UPS_SERIAL, NUT_USER, NUT_PASSWORD, MQTT_HOST, MQTT_TOPIC
# Create the NUT password secret file
mkdir -p .nut && echo "your_nut_password" > .nut/nut-upsd-password
docker compose up
```

The UPS USB device path defaults to `/dev/bus/usb/003`. Override with `UPS_USB_PATH` in `.env` if your UPS appears on a different path (check with `lsusb`).

## Environment variables

| Variable | Description | Default |
|---|---|---|
| `UPS_NAME` | NUT UPS name as configured in nut-upsd | `ups` |
| `UPS_HOST` | Hostname of the NUT server (use `nut-upsd` when running via this compose) | `nut-upsd` |
| `UPS_PORT` | NUT server port | `3493` |
| `MQTT_HOST` | Hostname or IP of the MQTT broker | `localhost` |
| `MQTT_PORT` | MQTT broker port | `1883` |
| `MQTT_TOPIC` | MQTT topic to publish UPS telemetry to | — |
| `SAMPLE_RATE_ONLINE` | Polling interval in seconds when UPS is online | `60` |
| `SAMPLE_RATE_OFFLINE` | Polling interval in seconds when UPS is offline | `10` |
| `UPS_SERIAL` | UPS serial number for nut-upsd device identification | — |
| `NUT_USER` | NUT authentication username | — |
| `NUT_PASSWORD` | NUT authentication password | — |
| `UPS_USB_PATH` | Host USB device path for the UPS (e.g. `/dev/bus/usb/003`) | `/dev/bus/usb/003` |

> **Note:** When deployed via `atlantis-controller`, the controller maps `UPS_SAMPLE_FREQUENCY` → `SAMPLE_RATE_ONLINE` and `UPS_BATTERY_SAMPLE_FREQUENCY` → `SAMPLE_RATE_OFFLINE` in its compose file. For standalone use, set `SAMPLE_RATE_ONLINE` and `SAMPLE_RATE_OFFLINE` directly.

## Secrets

The NUT password is passed via a Docker secret file rather than a plain environment variable:

| Secret | File path | Description |
|---|---|---|
| `nut-upsd-password` | `.nut/nut-upsd-password` | NUT daemon password |

## Deployment via atlantis-controller

When deployed as part of [atlantis-controller](https://github.com/your-org/atlantis-controller), this service is built and managed by the controller's `docker-compose.yml`. The controller's `.env` is the authoritative configuration source — this repo's `.env.example` and `docker-compose.yml` are for standalone use only.
