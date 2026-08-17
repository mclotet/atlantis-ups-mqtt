from atlantis_core.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    # Service-local field (not part of BaseServiceSettings) — deliberately not atl_*
    # prefixed; separate from group_id. This is the mission of the BRIDGED UPS
    # (identity.md §3.2 — "power": electrical power distribution/metering), used
    # to build the UPS's battery/status/availability topics. It is NOT this
    # bridge process's own edge_node_id (identity.md §5: containers are always
    # global/infra — see BRIDGE_EDGE_NODE_ID in main.py).
    mqtt_edge_node_id: str = "power"

    # The bridged UPS's own identity (identity.md §2.2 — "a device that reaches
    # the platform through a bridge carries its own device_id; the bridge is
    # transport, never identity"). Used for the battery/status topics and the
    # UPS's own availability topic (PLAT-244). Distinct from atl_device_id
    # (BaseServiceSettings), which is this BRIDGE PROCESS's own identity, used
    # for logging and the bridge's own availability/LWT.
    ups_device_id: str

    # NUT connection
    ups_name: str
    ups_host: str
    ups_port: str = "3493"

    # MQTT broker
    mqtt_host: str
    mqtt_port: int = 1883

    # Polling intervals (seconds)
    sample_rate_online: int = 60
    sample_rate_offline: int = 10

    # Reported in the MQTT birth message
    fw_version: str = "1.0.0"


def get_settings() -> Settings:
    return Settings()
