from abc import ABC, abstractmethod

from ups_mqtt.domain.models import UpsReading


class IUpsPort(ABC):
    @abstractmethod
    def read(self) -> UpsReading: ...
