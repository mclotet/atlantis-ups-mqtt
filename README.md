# atlantis-ups-mqtt

Polls a NUT (Network UPS Tools) daemon and publishes UPS telemetry to an MQTT broker.

The standalone `docker-compose.yml` includes both `nut-upsd` and `ups-mqtt` since they are tightly coupled — `nut-upsd` talks to the UPS over USB and exposes a NUT server; `ups-mqtt` queries it and forwards metrics to MQTT.

## Architecture

```text
APC Smart-UPS 750 (USB)
    → nut-upsd (usbhid-ups driver, NUT server)
        → ups-mqtt (runs `upsc` on SAMPLE_RATE_ONLINE/OFFLINE interval)
            → MQTT broker (battery/telemetry, ups/status, availability)
```

`ups-mqtt` holds no state of its own between polls — each cycle queries `nut-upsd` fresh and republishes. Built on `atlantis-core` (git submodule) for `BaseServiceSettings` configuration and `AtlantisLogger` structured logging.

## Standalone usage

Requires a physical UPS connected via USB and an MQTT broker reachable at `MQTT_HOST`.

```bash
git submodule update --init   # the Dockerfile copies libs/atlantis-core/python
cp .env.example .env
# Edit .env: set UPS_SERIAL, NUT_USER, NUT_PASSWORD, MQTT_HOST
# Create the NUT password secret file
mkdir -p .nut && echo "your_nut_password" > .nut/nut-upsd-password
docker compose up
```

The UPS USB device path defaults to `/dev/bus/usb/003`. Override with `UPS_USB_PATH` in `.env` if your UPS appears on a different path (check with `lsusb`).

## Environment variables

### ups-mqtt

Variables the service itself reads at runtime (`ups_mqtt/config.py`, `atlantis.toml`). Required ones have no safe default.

| Variable | Description | Default |
| --- | --- | --- |
| `UPS_NAME` | NUT UPS name as configured in nut-upsd | `ups` |
| `UPS_HOST` | Hostname of the NUT server (`nut-upsd` when running via this compose) | `nut-upsd` |
| `UPS_PORT` | NUT server port | `3493` |
| `MQTT_HOST` | Hostname or IP of the MQTT broker | `localhost` |
| `MQTT_PORT` | MQTT broker port | `1883` |
| `SAMPLE_RATE_ONLINE` | Polling interval in seconds when UPS is online | `60` |
| `SAMPLE_RATE_OFFLINE` | Polling interval in seconds when UPS is offline | `10` |
| `ATL_GROUP_ID` | Physical/logical location used in MQTT topic paths | `global` |
| `MQTT_EDGE_NODE_ID` | Mission of the bridged UPS (`power`); service-local, not an `ATL_*` platform field | `power` |
| `UPS_DEVICE_ID` | **Required.** Identity of the bridged UPS (`device_id` in the battery, status and UPS-availability topics), e.g. `apc-smartups750` | none (compose fallback `apc-smartups750`) |
| `ATL_DEVICE_ID` | Identity of this bridge process (logging, own availability topic and LWT under `infra`) | `ups-mqtt` |
| `ATL_SERVICE_NAME` | Service name used in structured log resource attributes | `ups-mqtt` |
| `ATL_ENV` | Environment: `dev`, `itg` or `pro` (`dev` for local/standalone runs only; deployed stacks use `itg` or `pro`) | `pro` |
| `LOG_FORMAT` | Stdout log format: `json` (OTel JSON) or `human` | `json` in compose |
| `ATL_LOG_LEVEL` | Minimum log level: `DEBUG`, `INFO`, `WARN`, `ERROR` (unknown values raise) | `WARNING` (`atlantis.toml`); compose falls back to `INFO` |
| `ATL_MQTT_LOG_MAX_PER_MINUTE` | Rate limit for MQTT log messages (0 = unlimited) | `300` |
| `FW_VERSION` | Service version reported in the MQTT availability birth message | `1.0.0` |

### nut-upsd (standalone compose only)

Consumed by the `nut-upsd` service in this repo's `docker-compose.yml`, not by `ups-mqtt`.

| Variable | Description | Default |
| --- | --- | --- |
| `UPS_SERIAL` | UPS serial number for device identification | none |
| `NUT_USER` | NUT authentication username | none |
| `NUT_PASSWORD` | NUT authentication password | none |
| `UPS_USB_PATH` | Host USB device path for the UPS | `/dev/bus/usb/003` |

## Published topics

Topics are built from `ATL_GROUP_ID`, `MQTT_EDGE_NODE_ID`, `UPS_DEVICE_ID` and `ATL_DEVICE_ID`; there is no `MQTT_TOPIC` variable. Retain follows the topic's message type (`atlantis_core.effective_retain`).

| Topic | Describes | Notes |
| --- | --- | --- |
| `atlantis/<group>/data/<edge>/<ups_device>/battery/telemetry` | the UPS | battery metrics; skipped when metrics are unavailable |
| `atlantis/<group>/state/<edge>/<ups_device>/ups/status` | the UPS | UPS state |
| `atlantis/<group>/availability/<edge>/<ups_device>/node/status` | the UPS | not LWT-backed; driven by each poll (`reason: "nut_unreachable"` when `upsc` stops answering) |
| `atlantis/<group>/availability/infra/<ATL_DEVICE_ID>/node/status` | this bridge process | birth on connect, LWT offline |

Polling runs every `SAMPLE_RATE_ONLINE` seconds while the UPS reports online, otherwise every `SAMPLE_RATE_OFFLINE`. Readings are dropped while no broker is connected; nothing is buffered across an outage.

## Key files

| Path | Responsibility |
| --- | --- |
| `main.py` | Composition root: settings, topics, MQTT client, poll loop |
| `ups_mqtt/config.py` | `Settings(BaseServiceSettings)` |
| `ups_mqtt/domain/` | UPS reading model and typed errors |
| `ups_mqtt/ports/` | `IUpsPort` and publisher ports |
| `ups_mqtt/application/` | `poll_and_publish`, `publish_ups_availability` |
| `ups_mqtt/adapters/nut/` | `NutAdapter`: runs the `upsc` binary (`nut-client` in the Dockerfile) |
| `ups_mqtt/adapters/mqtt/` | `MqttPublisher`: owns the paho client and topic strings |

## Secrets

The standalone compose gives `nut-upsd` the NUT password both as the Docker secret file below and as a `PASSWORD=${NUT_PASSWORD}` environment variable, so `NUT_PASSWORD` in `.env` is still required there.

| Secret | File path | Description |
| --- | --- | --- |
| `nut-upsd-password` | `.nut/nut-upsd-password` | NUT daemon password |

## Known limitations

These limitations apply to the APC Smart-UPS 750 running under the NUT `usbhid-ups` (USB HID) driver.

### `ups.load` always reports 0%

The `usbhid-ups` driver does not expose `ups.load` for this model over USB HID. The Grafana Load panel will always show 0%.

**Workaround A — serial port (apcsmart driver):** The Smart-UPS 750 has an RJ45 serial management port. The NUT `apcsmart` driver communicates over APC's proprietary serial protocol and does expose `ups.load`. This requires an APC RJ45-to-DB9 cable, a USB-to-serial adapter on the host, and a second NUT driver instance (or replacing the USB one).

**Workaround B — derive from Shelly EM:** If a Shelly Pro EM50 clamp monitors the UPS output circuit, load can be approximated as `(act_power_W / 500) * 100` (Smart-UPS 750 rated ~500 W). No new hardware is needed — a Grafana Flux query or a Telegraf processor is sufficient.

### `battery.runtime` reports 0 seconds

The UPS firmware has not produced a runtime estimate. This occurs when the battery is new or recently replaced and has not yet been calibrated.

**Fix:** Run a runtime calibration cycle via `upsrw` or the APC management interface. Once the UPS has discharged and recharged through the calibration cycle, the firmware reports a valid estimate and the panel updates automatically.

## Deployment via atlantis-controller

When deployed as part of [atlantis-controller](https://github.com/mclotet/atlantis-controller), this service is built and managed by the controller's `docker-compose.yml`. The service's own `.env.example` and `docker-compose.yml` are for standalone use only.

### How variables are set in atlantis-controller

The controller does **not** use this service's `.env` file. All variables are passed explicitly via the `environment` block in the controller's `docker-compose.yml`, sourced from the controller's own `.env` file.

The controller's `.env` uses prefixed variable names (`ATL_UPS_*`) to avoid collisions with the shelly-bridge service's `ATL_*` vars. The mapping is:

| Controller `.env` variable | Passed to `ups-mqtt` as |
| --- | --- |
| `UPS_SAMPLE_RATE_ONLINE` | `SAMPLE_RATE_ONLINE` |
| `UPS_SAMPLE_RATE_OFFLINE` | `SAMPLE_RATE_OFFLINE` |
| `ATL_UPS_GROUP_ID` | `ATL_GROUP_ID` |
| `ATL_UPS_EDGE_NODE_ID` | `MQTT_EDGE_NODE_ID` |
| `ATL_UPS_BRIDGED_DEVICE_ID` | `UPS_DEVICE_ID` |
| `ATL_UPS_DEVICE_ID` | `ATL_DEVICE_ID` |
| `ATL_UPS_SERVICE_NAME` | `ATL_SERVICE_NAME` |
| `ATL_UPS_ENV` | `ATL_ENV` |
| `ATL_UPS_LOG_LEVEL` | `ATL_LOG_LEVEL` |
| `ATL_UPS_MQTT_LOG_MAX_PER_MINUTE` | `ATL_MQTT_LOG_MAX_PER_MINUTE` |
| `UPS_FW_VERSION` | `FW_VERSION` |

`UPS_SERIAL`, `NUT_USER` and the NUT password (a Docker secret) go to the controller's `nut-upsd` service, not to `ups-mqtt`. `UPS_NAME`, `UPS_HOST`, `UPS_PORT`, `MQTT_HOST` and `MQTT_PORT` are hardcoded in the controller's `docker-compose.yml` because they are fixed by the stack topology.

> **Note:** Edit the `# UPS Monitoring` section in the controller's `.env` — not in this repo.
