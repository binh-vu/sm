import functools
from typing import Callable, List, Optional, Sequence, TypeVar, Union

import ray
from loguru import logger
from tqdm.auto import tqdm

R = TypeVar("R")
OBJECTS = {}
ray_initargs: dict = {}


def set_ray_init_args(**kwargs):
    global ray_initargs
    ray_initargs = kwargs


def ray_init(**kwargs):
    if not ray.is_initialized():
        logger.info("Initialize ray with args: {}", kwargs)
        ray.init(**kwargs)


def ray_put(val: R) -> "ray.ObjectRef[R]":
    global ray_initargs
    ray_init(**ray_initargs)
    return ray.put(val)


def ray_map(
    remote_fn: Callable[..., "ray.ObjectRef[R]"],
    args_lst: Sequence[Sequence],
    verbose: bool = False,
    poll_interval: float = 0.1,
    concurrent_submissions: int = 3000,
    desc: Optional[str] = None,
    debug: bool = False,
) -> List[R]:
    global ray_initargs

    if debug:
        # run in debug mode
        fn = remote_fn.__wrapped__
        output = []
        for arg in tqdm(args_lst, desc=desc, disable=not verbose):
            newarg = []
            for x in arg:
                if isinstance(x, ray.ObjectRef):
                    newarg.append(ray.get(x))
                else:
                    newarg.append(x)
            output.append(fn(*newarg))
        return output

    ray_init(**ray_initargs)

    n_jobs = len(args_lst)

    with tqdm(total=n_jobs, desc=desc, disable=not verbose) as pbar:
        output: List[R] = [None] * n_jobs  # type: ignore

        notready_refs = []
        ref2index = {}
        for i, args in enumerate(args_lst):
            # submit a task and add it to not ready queue and ref2index
            ref = remote_fn(*args)
            notready_refs.append(ref)
            ref2index[ref] = i

            # when the not ready queue is full, wait for some tasks to finish
            while len(notready_refs) >= concurrent_submissions:
                ready_refs, notready_refs = ray.wait(
                    notready_refs, timeout=poll_interval
                )
                pbar.update(len(ready_refs))
                for ref in ready_refs:
                    output[ref2index[ref]] = ray.get(ref)

        while len(notready_refs) > 0:
            ready_refs, notready_refs = ray.wait(notready_refs, timeout=poll_interval)
            pbar.update(len(ready_refs))
            for ref in ready_refs:
                output[ref2index[ref]] = ray.get(ref)

        return output


def enhance_error_info(msg: Callable[..., str]):
    def wrap_func(func):
        func_name = func.__name__

        @functools.wraps(func)
        def fn(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                raise Exception(
                    f"Failed to run {func_name} with {msg(*args, **kwargs)}"
                )

        return fn

    return wrap_func


def get_instance(constructor: Callable[[], R], name: Optional[str] = None) -> R:
    """A utility function to get a singleton, which can be created from the given constructor.

    One use case of this function is we have a big object that is expensive to send
    to individual task repeatedly. If the process are retrieved from a pool,
    this allows us to create the object per process instead of per task.
    """
    global OBJECTS

    if name is None:
        assert (
            constructor.__name__ != "<lambda>"
        ), "Cannot use lambda as a name because it will keep changing"
        name = constructor  # type: ignore

    if name not in OBJECTS:
        logger.trace("Create a new instance of {}", name)
        OBJECTS[name] = constructor()
    return OBJECTS[name]
