from ups_mqtt.domain.models import BatteryMetrics, UpsReading


def test_is_online_ol_status():
    r = UpsReading(status="OL", load=0, beeper_status="", delay_shutdown=0, battery=None)
    assert r.is_online() is True


def test_is_online_ob_status():
    r = UpsReading(status="OB", load=0, beeper_status="", delay_shutdown=0, battery=None)
    assert r.is_online() is False


def test_is_online_lb_status():
    r = UpsReading(status="LB", load=0, beeper_status="", delay_shutdown=0, battery=None)
    assert r.is_online() is False


def test_is_online_ol_chrg_lb_combined():
    # OL CHRG LB is a valid combined NUT status — contains OL so online
    r = UpsReading(status="OL CHRG LB", load=0, beeper_status="", delay_shutdown=0, battery=None)
    assert r.is_online() is True


def test_is_online_empty_status():
    r = UpsReading(status="", load=0, beeper_status="", delay_shutdown=0, battery=None)
    assert r.is_online() is False


def test_battery_metrics_fields():
    b = BatteryMetrics(
        charge=100.0,
        charge_low=10.0,
        runtime=2340.0,
        runtime_low=120.0,
        voltage=27.2,
        voltage_nominal=24.0,
    )
    assert b.charge == 100.0
    assert b.voltage_nominal == 24.0
