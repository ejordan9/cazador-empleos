from abc import ABC, abstractmethod

from src.models import Opportunity


class Collector(ABC):
    name: str

    @abstractmethod
    def collect(self) -> list[Opportunity]:
        """Devuelve las oportunidades crudas de esta fuente, ya en forma de Opportunity."""
        raise NotImplementedError
