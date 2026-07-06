from abc import ABC, abstractmethod
from asyncio import Lock

from smdb_logger import Logger


class BaseConnector(ABC):
    sync_lock: Lock

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def logger(self) -> Logger:
        pass
