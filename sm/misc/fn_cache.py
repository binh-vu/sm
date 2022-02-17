import functools
import os
from pathlib import Path

import orjson
from typing import Callable, Tuple, Any, Dict, Optional, Union, TypeVar


F = TypeVar("F", bound=Callable)


class CacheMethod:
    @staticmethod
    def single_object_arg(args, _kwargs):
        return id(args[0])

    @staticmethod
    def two_object_args(args, _kwargs):
        return (id(args[0]), id(args[1]))

    @staticmethod
    def three_object_args(args, _kwargs):
        return (id(args[0]), id(args[1]), id(args[2]))

    @staticmethod
    def as_is_posargs(args, _kwargs):
        return args

    @staticmethod
    def cache(
        key: Callable[[tuple, dict], Union[tuple, str, bytes, int]]
    ) -> Callable[[F], F]:
        """Cache instance's method during its life-time.
        Note: Order of the arguments is important. Different order of the arguments will result in different cache key.
        """

        def wrapper_fn(func):
            fn_name = func.__name__

            @functools.wraps(func)
            def fn(self, *args, **kwargs):
                if not hasattr(self, "_cache"):
                    self._cache = {}
                k = (fn_name, key(args, kwargs))
                if k not in self._cache:
                    self._cache[k] = func(self, *args, **kwargs)
                return self._cache[k]

            return fn

        return wrapper_fn  # type: ignore


def skip_if_file_exist(filepath: Union[Path, str]):
    """Skip running a function if a file exist"""

    def wrapper_fn(func):
        @functools.wraps(func)
        def fn(*args, **kwargs):
            if os.path.exists(filepath):
                return
            func(*args, **kwargs)

        return fn

    return wrapper_fn


def exec_or_skip_if_file_exist(filepath: Union[Path, str], skip: bool = False):
    """Skip running a function if a file exist. Otherwise, run it"""

    def wrapper_fn(func):
        @functools.wraps(func)
        def fn():
            if os.path.exists(filepath):
                return
            func()

        if not skip:
            fn()

    return wrapper_fn
