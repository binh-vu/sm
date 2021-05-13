import functools
from hashlib import md5
from pathlib import Path

import orjson
from slugify import slugify

from sm.misc.deser import deserialize_pkl, serialize_pkl
from sm.misc.remote_dict import PickleRedisStore


def redis_cache_func(url: str = "redis://localhost:6379", namespace: str = "", instance_method: bool = False):
    """
    - Cache a function, however, require that the arguments need hashable and pass by positions only (i.e., only *args, no **kwargs)
    - Allow an option to specify the namespace in case we have many function to cache.
    - Support caching instance method. However, it cannot observe all parameters that hidden in an instance
        so use it with caution
    """
    store = PickleRedisStore(url)

    if instance_method:
        def wrapper_instance_fn(func):
            @functools.wraps(func)
            def fn(*args):
                key = namespace + ":" + orjson.dumps(args[1:]).decode()
                if key not in store:
                    store[key] = func(*args)
                return store[key]

            return fn

        return wrapper_instance_fn

    def wrapper_fn(func):
        @functools.wraps(func)
        def fn(*args):
            key = namespace + ":" + orjson.dumps(args).decode()
            if key not in store:
                store[key] = func(*args)
            return store[key]

        return fn

    return wrapper_fn


def individual_file_cache(cache_dir: str):
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(exist_ok=True, parents=True)

    def wrapper_fn(func):
        @functools.wraps(func)
        def fn(*args):
            key = orjson.dumps(args)
            key = slugify(key) + "_" + md5(key).hexdigest()
            outfile = cache_dir / f"{key}.pkl"
            if not outfile.exists():
                resp = func(*args)
                serialize_pkl(resp, outfile)
                return resp
            return deserialize_pkl(outfile)

        return fn

    return wrapper_fn
