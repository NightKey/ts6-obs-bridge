from functools import wraps
from time import time_ns
from threading import Lock
from unittest import result

from modules import BaseConnector

open_calls_lock = Lock()
open_calls = {}

def async_wrapped(func):
    """
    Times the provided async function's runtime.
    """
    @wraps(func)
    async def async_timed_wrapper(self: BaseConnector, *args, **kwargs):
        key = f"{self.name}.{func.__name__}"
        self.logger.trace("Waiting for open_calls' lock")
        open_calls_lock.acquire()
        current_open = open_calls.get(key, 0)
        open_calls[key] = current_open + 1
        open_calls_lock.release()
        show_open_calls(self.logger.trace)
        self.logger.debug(f"Entering function {func.__name__}")
        start = time_ns()
        try:
            result = await func(self, *args, **kwargs)
            self.logger.debug(f"Function {func.__name__} returned '{result}'")
            return result
        finally:
            self.logger.debug(f"Function {func.__name__} exited after {(time_ns() - start)/1_000_000} ms")
            self.logger.trace("Waiting for open_calls' lock")
            open_calls_lock.acquire()
            current_open = open_calls.get(key, 0)
            open_calls[key] = current_open - 1
            if current_open <= 1:
                del open_calls[key]
            open_calls_lock.release()
            show_open_calls(self.logger.trace)
    return async_timed_wrapper

def async_sync(func):
    """
    Synchronizes async calls
    """
    @wraps(func)
    async def async_sync_wrapper(self: BaseConnector, *args, **kwargs):
        self.logger.debug(f"Acquiring sync-lock for {func.__name__}")
        await self.sync_lock.acquire()
        try:
            result = await func(self, *args, **kwargs)
            self.logger.debug(f"Synchronized function {func.__name__} finished")
            return result
        finally:
            self.logger.debug(f"Releasing sync-lock for {func.__name__}")
            self.sync_lock.release()

    return async_sync_wrapper

def show_open_calls(print) -> None:
    open_calls_lock.acquire()
    print(f"Open calls: {[name + '->' + str(amount) for name, amount in open_calls.items()] or 'None'}")
    open_calls_lock.release()