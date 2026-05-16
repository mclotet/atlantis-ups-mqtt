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
- Bumped `libs/atlantis-core` submodule from `af757e4` to `929aa84` (CORE-022 through CORE-024)
  - CORE-023: `MqttLogHandler` — camelCase keys, `uptime` as int, `edge_node.id` from `ATLANTIS_EDGE_NODE_ID`
  - CORE-024: `OtelJsonFormatter` — stdout always Format B; `LOG_FORMAT` env var; `timestampNs` field added
- Dockerfile updated: copies `ups_mqtt/` package + `main.py` + `atlantis.toml`; installs `atlantis-core[mqtt,config]`

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
