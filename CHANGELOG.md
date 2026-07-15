# Changelog

<!-- markdownlint-disable MD024 -->

All notable changes to this project will be documented in this file.
Format: Keep a Changelog (https://keepachangelog.com) — `[Unreleased]` / `[version] - YYYY-MM-DD`
Categories: Added | Changed | Deprecated | Removed | Fixed | Security

## [Unreleased]

### Added
- Hexagonal (ports-and-adapters) architecture: `ups_mqtt/` package with `domain/`, `ports/`, `application/`, `adapters/` layers
- `NutAdapter(IUpsPort)` — subprocess adapter for `upsc`, raises typed domain exceptions (`NutUnavailable`, `NutParseError`)
- `MqttPublisher` — encapsulates paho client and topic strings; skips battery publish gracefully when metrics unavailable
- `Settings(BaseServiceSettings)` — TOML-layered configuration via `atlantis_core.config`; secrets stay in `.env`
- `atlantis.toml` — committed deployment defaults (`atl_service_name`, `atl_device_id`, `atl_group_id`, `atl_env`, `atl_log_level`)
- `main.py` as composition root; old `ups_mqtt.py` removed
- 35 unit tests across five files (`test_domain`, `test_application`, `test_nut_adapter`, `test_mqtt_publisher`, `test_config`)
- `ATLANTIS_EDGE_NODE_ID` and `LOG_FORMAT=json` env vars in `docker-compose.yml` (required by CORE-023/024)

### Changed
- (CTRL-024) Bumped `libs/atlantis-core` submodule from `929aa84` to `bdc19e2` (CORE-048 through CORE-059), re-pinning past the CORE-048 Python/C++ MQTT builder alignment (`%.6g` telemetry number formatting) and the CORE-052 unsynced-timestamp fix; `pytest -q tests` passes 37/37 post-repin
  - Reviewed `test_mqtt_publisher.py`'s battery telemetry assertions against the `%.6g` formatting change: values still reflect real APC Smart-UPS 750 (`usbhid-ups`) precision, no truncation at the magnitudes this device reports
- Bumped reported MQTT `spec` in `main.py` from `1.29` to `1.30` (CORE-052 through CORE-059 fan-out, per MQTT Standard §1.6.1)

---

## [0.1.0] - 2026-04-01

### Added

- UPS → MQTT publisher for battery telemetry (`ups_power` measurement) and UPS status state (`ups_status`)
- AtlantisLogger integration with OTel JSON output and MQTT log forwarding
- MQTT exponential-backoff reconnection logic
- Environment variable configuration (`ATL_*` prefix) for broker, device, and credentials
- Docker image for deployment via atlantis-controller

### Fixed

- Updated atlantis-core to af757e4 — WiFi watchdog timer fix for stable connections
