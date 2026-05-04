# Changelog

All notable changes to this project will be documented in this file.
Format: Keep a Changelog (https://keepachangelog.com) — `[Unreleased]` / `[version] - YYYY-MM-DD`
Categories: Added | Changed | Deprecated | Removed | Fixed | Security

## [Unreleased]

## [0.1.0] - 2026-04-01

### Added
- UPS → MQTT publisher for battery telemetry (`ups_power` measurement) and UPS status state (`ups_status`)
- AtlantisLogger integration with OTel JSON output and MQTT log forwarding
- MQTT exponential-backoff reconnection logic
- Environment variable configuration (`ATL_*` prefix) for broker, device, and credentials
- Docker image for deployment via atlantis-controller

### Fixed
- Updated atlantis-core to af757e4 — WiFi watchdog timer fix for stable connections
