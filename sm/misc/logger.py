from abc import abstractmethod
from contextlib import contextmanager
from typing import Optional, Callable

_logger = None


class ContextLogger:
    @abstractmethod
    def log(self, msg: str, data: dict, mutual_data: dict):
        pass

    @abstractmethod
    def clear(self):
        pass


@contextmanager
def context_logger(context: dict, constructor: Optional[Callable[[dict], ContextLogger]] = None):
    global _logger

    if _logger is not None:
        raise Exception("Can't create nested logger")

    try:
        if constructor is None:
            _logger = ContextLogger()
        else:
            _logger = constructor(context)
        yield _logger
    finally:
        _logger.clear()
        _logger = None


def log(msg: str, **kwargs):
    """Log data into a container so that we
    Returns:
    """
    global _logger
    _logger.log(msg, kwargs)

