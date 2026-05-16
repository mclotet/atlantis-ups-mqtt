from dataclasses import dataclass


@dataclass
class BatteryMetrics:
    charge: float
    charge_low: float
    runtime: float
    runtime_low: float
    voltage: float
    voltage_nominal: float


@dataclass
class UpsReading:
    status: str           # raw ups.status string, e.g. "OL", "OB LB"
    load: float
    beeper_status: str
    delay_shutdown: float
    battery: BatteryMetrics | None  # None if any required field is missing/invalid

    def is_online(self) -> bool:
        return "OL" in self.status
