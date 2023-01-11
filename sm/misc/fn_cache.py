import functools
import os
from pathlib import Path

import orjson
from typing import (
    Callable,
    MutableMapping,
    Sequence,
    Any,
    Optional,
    Union,
    TypeVar,
)

F = TypeVar("F", bound=Callable)


class CacheMethod:
    @staticmethod
    def single_object_arg(args, _kwargs):
        return id(args[0])

    @staticmethod
    def single_literal_arg(args, _kwargs):
        return args[0]

    @staticmethod
    def two_object_args(args, _kwargs):
        return (id(args[0]), id(args[1]))

    @staticmethod
    def three_object_args(args, _kwargs):
        return (id(args[0]), id(args[1]), id(args[2]))

    @staticmethod
    def auto_object_args(args, _kwargs):
        return tuple(
            x if isinstance(x, (str, int, bool)) else id(x) for x in args
        )

    @staticmethod
    def as_is_posargs(args, _kwargs):
        return args

    @staticmethod
    def as_is(args, kwargs):
        return (args, tuple(kwargs.items()))

    @staticmethod
    def as_json(args, kwargs):
        return orjson.dumps((args, kwargs))

    @staticmethod
    def selected_args(selection: Sequence[Union[int, str]]):
        selected_args = sorted([x for x in selection if isinstance(x, int)])
        selected_kwargs = sorted([x for x in selection if isinstance(x, str)])

        def fn(args, kwargs):
            sargs = []
            skwargs = {}
            for i in selected_args:
                if i < len(args):
                    sargs.append(args[i])
            for k in selected_kwargs:
                if k in kwargs:
                    skwargs[k] = kwargs[k]
            return orjson.dumps((sargs, skwargs))

        return fn

    @staticmethod
    def cache(
        key: Callable[[tuple, dict], Union[tuple, str, bytes, int]],
        cache_attr: str = "_cache",
    ) -> Callable[[F], F]:
        """Cache instance's method during its life-time.
        Note: Order of the arguments is important. Different order of the arguments will result in different cache key.
        """

        def wrapper_fn(func):
            fn_name = func.__name__

            @functools.wraps(func)
            def fn(self, *args, **kwargs):
                if not hasattr(self, cache_attr):
                    setattr(self, cache_attr, {})
                cache = getattr(self, cache_attr)
                k = (fn_name, key(args, kwargs))
                if k not in cache:
                    cache[k] = func(self, *args, **kwargs)
                return cache[k]

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


def cache_fn(
    cache: MutableMapping[bytes, Any],
    key: Optional[Callable[[str, tuple, dict], bytes]] = None,
) -> Callable[[F], F]:
    def wrapper_fn(func):
        fn_name = func.__name__

        @functools.wraps(func)
        def fn(self, *args, **kwargs):

            k = orjson.dumps((fn_name, args, kwargs))
            if k not in cache:
                cache[k] = func(self, *args, **kwargs)
            return cache[k]

        return fn

    return wrapper_fn  # type: ignore
