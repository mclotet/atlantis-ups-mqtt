import pytest


def test_settings_loads_from_toml_and_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "atlantis.toml").write_text(
        'atl_service_name = "ups-mqtt"\n'
        'atl_device_id    = "ups-mqtt"\n'
        'atl_group_id     = "global"\n'
        'mqtt_edge_node_id = "power"\n'
        'ups_device_id    = "apc-smartups750"\n'
        'atl_env          = "pro"\n'
        'atl_log_level    = "WARNING"\n'
        'ups_name         = "ups"\n'
        'ups_host         = "nut-upsd"\n'
        'mqtt_host        = "broker"\n'
    )
    from ups_mqtt.config import Settings
    s = Settings()
    assert s.atl_service_name == "ups-mqtt"
    assert s.atl_device_id    == "ups-mqtt"
    assert s.atl_group_id     == "global"
    assert s.mqtt_edge_node_id == "power"
    assert s.ups_device_id    == "apc-smartups750"
    assert s.ups_name         == "ups"
    assert s.ups_host         == "nut-upsd"
    assert s.mqtt_host        == "broker"
    assert s.ups_port         == "3493"
    assert s.mqtt_port        == 1883
    assert s.sample_rate_online  == 60
    assert s.sample_rate_offline == 10


def test_env_var_overrides_toml(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "atlantis.toml").write_text(
        'atl_log_level = "WARNING"\n'
        'ups_name      = "ups"\n'
        'ups_host      = "nut-upsd"\n'
        'mqtt_host     = "broker"\n'
        'ups_device_id = "apc-smartups750"\n'
    )
    monkeypatch.setenv("ATL_LOG_LEVEL", "DEBUG")
    from ups_mqtt.config import Settings
    s = Settings()
    assert s.atl_log_level == "DEBUG"


def test_missing_required_field_raises(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "atlantis.toml").write_text("")
    from pydantic import ValidationError
    from ups_mqtt.config import Settings
    with pytest.raises(ValidationError):
        Settings()


def test_missing_ups_device_id_raises(tmp_path, monkeypatch):
    # ups_device_id (PLAT-244) has no default, unlike mqtt_edge_node_id — the
    # bridged UPS's identity must always be set explicitly, never guessed.
    monkeypatch.chdir(tmp_path)
    (tmp_path / "atlantis.toml").write_text(
        'atl_service_name = "ups-mqtt"\n'
        'atl_device_id    = "ups-mqtt"\n'
        'atl_group_id     = "global"\n'
        'atl_env          = "pro"\n'
        'atl_log_level    = "WARNING"\n'
        'ups_name         = "ups"\n'
        'ups_host         = "nut-upsd"\n'
        'mqtt_host        = "broker"\n'
    )
    from pydantic import ValidationError
    from ups_mqtt.config import Settings
    with pytest.raises(ValidationError):
        Settings()


def test_atl_device_id_and_ups_device_id_are_independent(tmp_path, monkeypatch):
    # PLAT-244 regression guard: the bridge's own identity and the bridged
    # UPS's identity must be settable to different values and never conflated.
    monkeypatch.chdir(tmp_path)
    (tmp_path / "atlantis.toml").write_text(
        'atl_service_name = "ups-mqtt"\n'
        'atl_device_id    = "ups-mqtt"\n'
        'atl_group_id     = "global"\n'
        'mqtt_edge_node_id = "power"\n'
        'ups_device_id    = "apc-smartups750"\n'
        'atl_env          = "pro"\n'
        'atl_log_level    = "WARNING"\n'
        'ups_name         = "ups"\n'
        'ups_host         = "nut-upsd"\n'
        'mqtt_host        = "broker"\n'
    )
    monkeypatch.setenv("UPS_DEVICE_ID", "apc-smartups750-b")
    from ups_mqtt.config import Settings
    s = Settings()
    assert s.atl_device_id != s.ups_device_id
    assert s.atl_device_id == "ups-mqtt"
    assert s.ups_device_id == "apc-smartups750-b"  # env overrides toml, per BaseServiceSettings priority
