from abc import ABC, abstractmethod


class ProviderError(RuntimeError):
    pass


class StockProvider(ABC):
    name: str
    @abstractmethod
    def fetch(self, query, destination): ...


class TTSProvider(ABC):
    name: str
    @abstractmethod
    def synthesize(self, text, destination, voice): ...


class MusicProvider(ABC):
    name: str
    @abstractmethod
    def fetch(self, query, destination): ...
