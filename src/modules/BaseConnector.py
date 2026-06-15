from abc import ABC, abstractmethod

from smdb_logger import Logger


class BaseConnector(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def logger(self) -> Logger:
        pass
