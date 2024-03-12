import functools
import sqlite3
import sys
import time
from pathlib import Path
from typing import (
    Any,
    Callable,
    List,
    Literal,
    Optional,
    Sequence,
    Type,
    TypeVar,
    Union,
    cast,
    overload,
)

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


@overload
def ray_put(val: R, using_ray: Literal[True] = True) -> "ray.ObjectRef[R]": ...


@overload
def ray_put(val: R, using_ray: Literal[False]) -> R: ...


@overload
def ray_put(val: R, using_ray: bool) -> Union["ray.ObjectRef[R]", R]: ...


def ray_put(val: R, using_ray: bool = True) -> Union["ray.ObjectRef[R]", R]:
    global ray_initargs
    if not using_ray:
        return val
    ray_init(**ray_initargs)
    return ray.put(val)


def ray_get_num_gpu() -> float:
    ray_init(**ray_initargs)
    return ray.available_resources().get("GPU", 0)


def ray_map(
    fn: Union[Callable[..., "ray.ObjectRef[R]"], Callable[..., R]],
    args_lst: Sequence[Sequence],
    verbose: bool = False,
    poll_interval: float = 0.1,
    concurrent_submissions: int = 3000,
    desc: Optional[str] = None,
    using_ray: bool = True,
    is_func_remote: bool = True,
    remote_options: Optional[dict] = None,
    before_shutdown: Optional[Callable[[Any], Any]] = None,
    auto_shutdown: bool = False,
) -> List[R]:
    """
    Args:
        before_shutdown: if you use numpy arrays, shutdown ray cluster will released the shared memory and thus, may corrupt the arrays later. You should use
            before_shutdown to copy the data before shutdown. This only applies to the case where using_ray=True && auto_shutdown=True.
    """
    global ray_initargs

    if not using_ray:
        # run locally without ray, usually for debugging
        if is_func_remote:
            localfn: Callable[..., R] = fn.__wrapped__
        else:
            localfn = cast(Callable[..., R], fn)
        output = []
        for arg in tqdm(args_lst, desc=desc, disable=not verbose or len(args_lst) <= 1):
            newarg = []
            for x in arg:
                if isinstance(x, ray.ObjectRef):
                    newarg.append(ray.get(x))
                else:
                    newarg.append(x)
            try:
                output.append(localfn(*newarg))
            except:
                logger.error("ray_map failed at item index {}", len(output))
                raise
        return output

    ray_init(**ray_initargs)

    n_jobs = len(args_lst)

    if is_func_remote:
        remote_fn = cast(Callable[..., "ray.ObjectRef[R]"], fn)
    else:
        if remote_options is None:
            wrapper = ray.remote
        else:
            wrapper = ray.remote(**remote_options)
        remote_fn: Callable[..., "ray.ObjectRef[R]"] = wrapper(fn).remote  # type: ignore

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
                    try:
                        output[ref2index[ref]] = ray.get(ref)
                    except:
                        logger.error("ray_map failed at item index {}", ref2index[ref])
                        raise

        while len(notready_refs) > 0:
            ready_refs, notready_refs = ray.wait(notready_refs, timeout=poll_interval)
            pbar.update(len(ready_refs))
            for ref in ready_refs:
                try:
                    output[ref2index[ref]] = ray.get(ref)
                except:
                    logger.error("ray_map failed at item index {}", ref2index[ref])
                    raise

        if auto_shutdown:
            if before_shutdown is not None:
                output = [before_shutdown(x) for x in output]
            ray.shutdown()
        return output


def ray_actor_map(
    actor_class: Type,
    actor_fn: str,
    actor_args_lst: Sequence[Sequence],
    args_lst: Sequence[Sequence],
    verbose: bool = False,
    poll_interval: float = 0.1,
    concurrent_submissions: int = 3000,
    desc: Optional[str] = None,
    using_ray: bool = True,
    is_actor_remote: bool = True,
    remote_options: Optional[dict] = None,
    before_shutdown: Optional[Callable[[Any], Any]] = None,
    auto_shutdown: bool = False,
):
    """
    Args:
        before_shutdown: if you use numpy arrays, shutdown ray cluster will released the shared memory and thus, may corrupt the arrays later. You should use
            before_shutdown to copy the data before shutdown. This only applies to the case where using_ray=True && auto_shutdown=True.
    """
    global ray_initargs

    if not using_ray:
        # assert all actors are local
        assert (
            not is_actor_remote
        ), "If you want to run it locally, do not wrap the actor class with ray.remote"
        actors = [actor_class(*args) for args in actor_args_lst]
        actor_fns = [getattr(actor, actor_fn) for actor in actors]

        output = []
        i = 0
        for arg in tqdm(args_lst, desc=desc, disable=not verbose):
            newarg = []
            for x in arg:
                if isinstance(x, ray.ObjectRef):
                    newarg.append(ray.get(x))
                else:
                    newarg.append(x)
            try:
                output.append(actor_fns[i % len(actors)](*newarg))
            except:
                logger.error("ray_actor_map failed at item index {}", len(output))
                raise
            i += 1
        return output

    ray_init(**ray_initargs)

    if not is_actor_remote:
        if remote_options is None:
            actor_class = ray.remote(actor_class)
        else:
            actor_class = ray.remote(**remote_options)(actor_class)

    actors = [actor_class.remote(*args) for args in actor_args_lst]
    actor_fns = [getattr(actor, actor_fn).remote for actor in actors]

    n_jobs = len(args_lst)
    with tqdm(total=n_jobs, desc=desc, disable=not verbose) as pbar:
        output: list = [None] * n_jobs

        notready_refs = []
        ref2index = {}
        for i, args in enumerate(args_lst):
            # submit a task and add it to not ready queue and ref2index
            ref = actor_fns[i % len(actors)](*args)
            notready_refs.append(ref)
            ref2index[ref] = i

            # when the not ready queue is full, wait for some tasks to finish
            while len(notready_refs) >= concurrent_submissions:
                ready_refs, notready_refs = ray.wait(
                    notready_refs, timeout=poll_interval
                )
                pbar.update(len(ready_refs))
                for ref in ready_refs:
                    try:
                        output[ref2index[ref]] = ray.get(ref)
                    except:
                        logger.error(
                            "ray_actor_map failed at item index {}", ref2index[ref]
                        )
                        raise

        while len(notready_refs) > 0:
            ready_refs, notready_refs = ray.wait(notready_refs, timeout=poll_interval)
            pbar.update(len(ready_refs))
            for ref in ready_refs:
                try:
                    output[ref2index[ref]] = ray.get(ref)
                except:
                    logger.error(
                        "ray_actor_map failed at item index {}", ref2index[ref]
                    )
                    raise

        if auto_shutdown:
            if before_shutdown is not None:
                output = [before_shutdown(x) for x in output]
            ray.shutdown()

        return output


def enhance_error_info(getid: Union[Callable[..., str], str]):
    """Enhancing error report by printing out tracable id of the input arguments.

    Args:
        getid: a function that takes the same arguments as the wrapped function and return a tracable id.
            If msg is a string, it is a list of accessors joined by dot. Each accessor is either a number
            (to call __getitem__) or a string (to call __getattr__). The first accessor is always the number
            which is the argument index that will be used to extract the traceable id from. For example: 0.table.table_id
    """

    if isinstance(getid, str):

        def get_id_fn(*args, **kwargs):
            assert len(kwargs) == 0
            ptr = args
            for accessor in getid.split("."):
                if accessor.isdigit():
                    ptr = ptr[int(accessor)]
                else:
                    ptr = getattr(ptr, accessor)
            return ptr

    else:
        get_id_fn = getid

    def wrap_func(func):
        func_name = func.__name__

        @functools.wraps(func)
        def fn(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except BaseException as e:
                if hasattr(sys, "gettrace") and sys.gettrace() is not None:
                    # for debug mode in vscode...
                    logger.error(
                        f"Failed to run {func_name} with {get_id_fn(*args, **kwargs)}"
                    )
                    raise
                else:
                    raise Exception(
                        f"Failed to run {func_name} with {get_id_fn(*args, **kwargs)}"
                    ) from e

        return fn

    return wrap_func


def track_runtime(getid: Union[Callable[..., str], str], outfile: Union[str, Path]):
    if isinstance(getid, str):

        def get_id_fn(*args, **kwargs):
            assert len(kwargs) == 0
            ptr = args
            for accessor in getid.split("."):
                if accessor.isdigit():
                    ptr = ptr[int(accessor)]
                else:
                    ptr = getattr(ptr, accessor)
            return ptr

    else:
        get_id_fn = getid

    init_db = not Path(outfile).exists()
    db = sqlite3.connect(outfile)
    if init_db:
        with db:
            db.execute("CREATE TABLE timesheet(func TEXT, name TEXT, time REAL)")

    def wrap_func(func):
        func_name = func.__name__

        @functools.wraps(func)
        def fn(*args, **kwargs):
            start = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                end = time.time()
                with db:
                    db.execute(
                        "INSERT INTO timesheet VALUES (:func, :name, :time)",
                        {
                            "func": func_name,
                            "name": get_id_fn(*args, **kwargs),
                            "time": end - start,
                        },
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
