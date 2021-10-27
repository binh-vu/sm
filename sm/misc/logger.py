from __future__ import annotations
import threading
from abc import abstractmethod
from contextlib import contextmanager
from typing import Optional, Callable


_container = threading.local()
_container.logger = None


class ContextLogger:
    @abstractmethod
    def log(self, ns: str, data: dict, mutual_data: dict):
        pass

    @abstractmethod
    def clear(self):
        pass


@contextmanager
def context_logger(
    context: dict, constructor: Optional[Callable[[dict], ContextLogger]] = None
):
    global _container

    if _container.logger is not None:
        raise Exception("Can't create nested logger")

    try:
        _container.logger = (
            ContextLogger() if constructor is None else constructor(context)
        )
        yield _container.logger
    finally:
        if _container.logger is not None:
            _container.logger.clear()
        _container.logger = None


def log(ns: str, data: Optional[dict] = None, mutual_data: Optional[dict] = None):
    global _container

    if _container.logger is not None:
        _container.logger.log(ns, data or {}, mutual_data or {})
