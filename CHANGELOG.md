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
- (CORE-122) Bumped `libs/atlantis-core` submodule from `32c4425` to `53ba4f1` (CORE-122: MQTT retain policy). Retain is now derived from the topic's message type inside atlantis-core rather than passed at the call site, so all five `retain=` literals here are replaced by `atlantis_core.effective_retain(topic)`. Behaviour-preserving — the CORE-122 fleet audit confirmed every publish in this service already matched MQTT §5.2 (availability/state retained, battery telemetry not); `pytest -q` passes 37/37 post-repin. Pins `53ba4f1` rather than `e1139ff` deliberately: `e1139ff` shipped a top-level `__init__` that re-exported `Severity` from `atlantis_core.health` while the defining changes were still uncommitted, breaking `import atlantis_core` outright
- Bumped reported MQTT `spec` in `main.py` from `1.30` to `1.31` (CORE-122 fan-out, per MQTT Standard §1.6.1 rule 3 — conformance verified, not assumed)
- (CTRL-032) Bumped `libs/atlantis-core` submodule from `bdc19e2` to `32c4425` (CORE-064 through CORE-074: WiFi PSK rotation, WiFi NVS host-side provisioning + Infisical secret-sync, HTTPS transport, configurable MQTT buffer size, retirement of a dead WiFi password macro): all 24 pulled-in commits are ESP32/C++-side or additive Python provisioning tooling (new `atlantis_core.provisioning` module, `provisioning` optional-extra, `Dockerfile`) behind a new `[project.scripts]` entry point — `config.py`, `mqtt_payload.py`, `mqtt_topics.py`, `logging/`, `health/`, and `defaults.toml` (the `[mqtt,config]` extras this service actually installs) are byte-for-byte unchanged; `pytest -q` passes 37/37 post-repin
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
