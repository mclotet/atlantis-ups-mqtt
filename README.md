# atlantis-ups-mqtt

Polls a NUT (Network UPS Tools) daemon and publishes UPS telemetry to an MQTT broker.

The standalone `docker-compose.yml` includes both `nut-upsd` and `ups-mqtt` since they are tightly coupled — `nut-upsd` talks to the UPS over USB and exposes a NUT server; `ups-mqtt` queries it and forwards metrics to MQTT.

## Standalone usage

Requires a physical UPS connected via USB and an MQTT broker reachable at `MQTT_HOST`.

```bash
cp .env.example .env
# Edit .env: set UPS_SERIAL, NUT_USER, NUT_PASSWORD, MQTT_HOST
# Create the NUT password secret file
mkdir -p .nut && echo "your_nut_password" > .nut/nut-upsd-password
docker compose up
```

The UPS USB device path defaults to `/dev/bus/usb/003`. Override with `UPS_USB_PATH` in `.env` if your UPS appears on a different path (check with `lsusb`).

## Environment variables

These are the variables the service itself reads at runtime (as defined in `.env.example`):

| Variable | Description | Default |
| --- | --- | --- |
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
| `UPS_USB_PATH` | Host USB device path for the UPS | `/dev/bus/usb/003` |
| `ATL_GROUP_ID` | Physical/logical location used in MQTT topic paths | `global` |
| `ATL_EDGE_NODE_ID` | Logical subsystem type (e.g. `rack`) | `rack` |
| `ATL_DEVICE_ID` | Unique identifier of the host running this service | `raspberrypi5` |
| `ATL_SERVICE_NAME` | Service name used in structured log resource attributes | `ups-mqtt` |
| `ATL_ENV` | Logging format: `development` = human-readable, `production` = OTel JSON | `production` |
| `ATL_LOG_LEVEL` | Minimum log level: `DEBUG`, `INFO`, `WARN`, `ERROR` | `INFO` |
| `ATL_MQTT_LOG_MAX_PER_MINUTE` | Rate limit for MQTT log messages (0 = unlimited) | `300` |
| `FW_VERSION` | Service version reported in the MQTT availability birth message | `1.0.0` |

## Secrets

The NUT password is passed via a Docker secret file rather than a plain environment variable:

| Secret | File path | Description |
| --- | --- | --- |
| `nut-upsd-password` | `.nut/nut-upsd-password` | NUT daemon password |

## Deployment via atlantis-controller

When deployed as part of [atlantis-controller](https://github.com/mclotet/atlantis-controller), this service is built and managed by the controller's `docker-compose.yml`. The service's own `.env.example` and `docker-compose.yml` are for standalone use only.

### How variables are set in atlantis-controller

The controller does **not** use this service's `.env` file. All variables are passed explicitly via the `environment` block in the controller's `docker-compose.yml`, sourced from the controller's own `.env` file.

The controller's `.env` uses prefixed variable names (`ATL_UPS_*`) to avoid collisions with the shelly-bridge service's `ATL_*` vars. The mapping is:

| Controller `.env` variable | Passed to container as |
| --- | --- |
| `UPS_SERIAL` | `UPS_SERIAL` |
| `NUT_USER` | `NUT_USER` |
| `NUT_PASSWORD` | `NUT_PASSWORD` |
| `UPS_SAMPLE_RATE_ONLINE` | `SAMPLE_RATE_ONLINE` |
| `UPS_SAMPLE_RATE_OFFLINE` | `SAMPLE_RATE_OFFLINE` |
| `ATL_UPS_GROUP_ID` | `ATL_GROUP_ID` |
| `ATL_UPS_EDGE_NODE_ID` | `ATL_EDGE_NODE_ID` |
| `ATL_UPS_DEVICE_ID` | `ATL_DEVICE_ID` |
| `ATL_UPS_SERVICE_NAME` | `ATL_SERVICE_NAME` |
| `ATL_UPS_ENV` | `ATL_ENV` |
| `ATL_UPS_LOG_LEVEL` | `ATL_LOG_LEVEL` |
| `ATL_UPS_MQTT_LOG_MAX_PER_MINUTE` | `ATL_MQTT_LOG_MAX_PER_MINUTE` |
| `UPS_FW_VERSION` | `FW_VERSION` |

Several variables (`UPS_NAME`, `UPS_HOST`, `UPS_PORT`, `MQTT_HOST`, `MQTT_PORT`) are hardcoded in the controller's `docker-compose.yml` because they are fixed by the stack topology. Topics are built internally from `ATL_*` vars — there is no `MQTT_TOPIC` variable.

> **Note:** Edit the `# UPS Monitoring` section in the controller's `.env` — not in this repo.
