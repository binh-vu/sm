import functools

import orjson
from typing import Callable, Tuple, Any, Dict, Optional

from sm.misc.big_dict.rocksdb import PickleRocksDBStore
from sm.misc.big_dict.redis import PickleRedisStore

CACHE = {}


def cache_func(
    dbfile: str = "/tmp/cache_func.db",
    namespace: str = "",
    get_key: Callable[[str, str, Tuple[Any, ...], Dict[str, Any]], str] = None,
    instance_method: bool = False,
    cache: Optional[dict] = None,
):
    """Cache a function

    Args:
        dbfile: can be redis (e.g., "redis://localhost:6379") or rocksdb (local file)
        namespace:
        get_key:
        instance_method:
        cache:

    Returns:

    """
    global CACHE
    if cache is None:
        cache = CACHE

    if dbfile not in cache:
        if dbfile.startswith("redis://"):
            db = PickleRedisStore(dbfile)
        else:
            db = PickleRocksDBStore(dbfile)
        cache[dbfile] = db
    db = cache[dbfile]

    if get_key is None:
        get_key = default_get_key

    if instance_method:

        def wrapper_instance_fn(func):
            fn_name = func.__name__

            @functools.wraps(func)
            def fn(*args, **kwargs):
                key = get_key(namespace, fn_name, args[1:], kwargs)
                if key not in db:
                    db[key] = func(*args, **kwargs)
                return db[key]

            return fn

        return wrapper_instance_fn

    def wrapper_fn(func):
        fn_name = func.__name__

        @functools.wraps(func)
        def fn(*args, **kwargs):
            key = get_key(namespace, fn_name, args, kwargs)
            if key not in db:
                db[key] = func(*args, **kwargs)
            return db[key]

        return fn

    return wrapper_fn


def default_get_key(namespace, func_name, args, kwargs):
    return orjson.dumps(
        {"ns": namespace, "fn": func_name, "a": args, "kw": kwargs}
    ).decode()
