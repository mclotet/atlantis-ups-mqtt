from atlantis_core.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    # Service-local field (not part of BaseServiceSettings) — deliberately not atl_*
    # prefixed; separate from group_id, used to build MQTT topics
    mqtt_edge_node_id: str = "rack"

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
