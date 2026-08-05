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


class TextProvider(ABC):
    name: str
    @abstractmethod
    def generate(self, prompt, *, system=None, max_tokens=2048, temperature=1.0): ...
