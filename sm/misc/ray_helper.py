from __future__ import annotations

import functools
import pickle
import sqlite3
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from email.policy import default
from pathlib import Path
from traceback import format_exception
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

import httpx
import numpy as np
import orjson
from loguru import logger
from sm.misc.funcs import get_classpath, import_attr
from tqdm.auto import tqdm

try:
    import ray

    has_ray = True
except ImportError:
    has_ray = False

try:
    from starlette.requests import Request
    from starlette.responses import Response
except ImportError:
    ...


@dataclass
class RayScope:
    allow_parallel: bool
    actors: dict[str, list["ray.ObjectRef"]] = field(default_factory=dict)

    def kill_actors(self, ns: Optional[str] = None):
        if ns is None:
            for actors in self.actors.values():
                for actor in actors:
                    ray.kill(actor)
            self.actors = {}
        else:
            for actor in self.actors.get(ns, []):
                ray.kill(actor)
            self.actors.pop(ns, None)

    def num_actors(self) -> int:
        return sum(len(actors) for actors in self.actors.values())


class RemoteService:
    def __init__(self, constructor: Union[type, Callable], args: tuple):
        self.object = constructor(*args)
        self.classpath = get_classpath(self.object.__class__)
        self.classargs = args

    async def __call__(self, req: "Request") -> dict | tuple | "Response":
        req = pickle.loads(await req.body())
        if req["method"] == "__meta__":
            return self.classpath, self.classargs
        try:
            return {
                "return": getattr(self.object, req["method"])(
                    *req.get("args", tuple()), **req.get("kwargs", {})
                )
            }
        except Exception as e:
            return Response(
                orjson.dumps(
                    {
                        "exception": get_classpath(e.__class__),
                        "message": str(e),
                        "stack_trace": "".join(format_exception(e)),
                    }
                ).decode(),
                media_type="application/json",
                status_code=500,
            )

    @staticmethod
    def start(
        clz: Union[type, Callable],
        args: tuple,
        options: Optional[dict] = None,
        name: Optional[str] = None,
        blocking: bool = False,
    ):
        """Deploy a service on Ray cluster.

        Args:
            clz: constructor
            args: arguments to the constructor
            options: options to deploy the service
            name: name of the service
            blocking: whether to block the main thread so users can run Ctrl+C to stop the service
        """
        from ray import serve

        serve.run(
            serve.deployment(name=name or clz.__name__, **(options or {}))(
                RemoteService
            ).bind(constructor=clz, args=args),
            blocking=blocking,
        )


class RemoteClient:
    @dataclass
    class RPC:
        slf: "RemoteClient"
        name: str

        def __call__(self, *args, **kwargs) -> Any:
            r = httpx.post(
                self.slf.endpoint,
                content=pickle.dumps(
                    {
                        "method": self.name,
                        "args": args,
                        "kwargs": kwargs,
                    }
                ),
                timeout=None,
            )
            if r.status_code != 200:
                try:
                    data = r.json()
                    exception_cls = import_attr(data["exception"])
                    exception = exception_cls(
                        data["message"] + "\n.Stack trace:\n" + data["stack_trace"]
                    )
                except:
                    logger.error("Failed to reconstruct the exception", exc_info=True)
                    raise Exception(
                        f"(Check log for more info) Failed to call {self.name}. Response ({r.status_code}), reason: {r.text}"
                    )
                raise exception

            return r.json()["return"]

    def __init__(self, cls: type, args: tuple, endpoint: str):
        self.cls = cls
        self.args = args
        self.endpoint = endpoint
        self.is_validated = False

    def __getattr__(self, name: str) -> Any:
        if not self.is_validated:
            # only validate once when we actually use the service
            # if the remote service is correct...
            classpath, classargs = (
                httpx.post(
                    self.endpoint,
                    content=pickle.dumps({"method": "__meta__"}),
                    timeout=None,
                )
                .raise_for_status()
                .json()
            )
            if not (
                classpath == get_classpath(self.cls) and tuple(classargs) == self.args
            ):
                raise ValueError(
                    f"Remote service is not correct. Get ({classpath})({classargs}) instead of ({get_classpath(self.cls)})({self.args})"
                )
            self.is_validated = True

        return RemoteClient.RPC(self, name)


R = TypeVar("R")
OBJECTS = {}
ray_initargs: dict = {}
ray_scopes: list[RayScope] = []


def require_ray(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not has_ray:
            raise ImportError("ray is required for function: %s" % func.__name__)
        return func(*args, **kwargs)

    return wrapper


def is_parallelizable() -> bool:
    """Check whether the current context is parallelable."""
    global ray_scopes
    return len(ray_scopes) > 0 and ray_scopes[-1].allow_parallel


@contextmanager
def allow_parallel():
    """Mark this code block as parallelizable."""
    global ray_scopes

    try:
        ray_scopes.append(RayScope(allow_parallel=True))
        yield
    finally:
        scope = ray_scopes.pop()
        scope.kill_actors()


@contextmanager
def no_parallel():
    """Mark this code block as non-parallelizable."""
    global ray_scopes

    try:
        ray_scopes.append(RayScope(allow_parallel=False))
        yield
    finally:
        scope = ray_scopes.pop()
        assert scope.num_actors() == 0


def set_ray_init_args(**kwargs):
    global ray_initargs
    ray_initargs = kwargs


@require_ray
def add_ray_actors(
    cls: type[R],
    args: tuple,
    ns: str,
    size: int = 1,
    scope: int = -1,
    remote_options: Optional[dict] = None,
) -> list["ray.ObjectRef[R]"]:
    """Create a ray actor and return the actor ref. Also, store the actor ref in an scope identified by the index.

    Args:
        cls: the class of the actor.
        args: the arguments to create the actor.
        size: number of actors to create
        scope: scope index
    """
    global ray_scopes
    scope_data = ray_scopes[scope]
    assert scope_data.allow_parallel, "Cannot create actors in a non-parallel context"
    if ns not in scope_data.actors:
        scope_data.actors[ns] = []

    if len(scope_data.actors[ns]) < size and remote_options is not None:
        wrapper = ray.remote(**remote_options)
    else:
        wrapper = ray.remote

    while len(scope_data.actors[ns]) < size:
        scope_data.actors[ns].append(wrapper(cls).remote(*args))
    return scope_data.actors[ns]


def get_ray_actors(ns: str, scope: int = -1) -> list["ray.ObjectRef"]:
    global ray_scopes
    scope_data = ray_scopes[scope]
    assert scope_data.allow_parallel, "Cannot create actors in a non-parallel context"
    return scope_data.actors.get(ns, [])


@require_ray
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


@require_ray
def ray_put(val: R, using_ray: bool = True) -> Union["ray.ObjectRef[R]", R]:
    global ray_initargs
    if not using_ray:
        return val
    ray_init(**ray_initargs)
    return ray.put(val)


def ray_get(val: "ray.ObjectRef[R]") -> R:
    obj = ray.get(val)
    if isinstance(obj, np.ndarray):
        return np.copy(obj)  # type: ignore
    return obj


@require_ray
def ray_shutdown():
    ray.shutdown()


@require_ray
def ray_get_num_gpu() -> float:
    ray_init(**ray_initargs)
    return ray.available_resources().get("GPU", 0)


@require_ray
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
                    newarg.append(ray_get(x))
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
                        output[ref2index[ref]] = ray_get(ref)
                    except:
                        logger.error("ray_map failed at item index {}", ref2index[ref])
                        raise

        while len(notready_refs) > 0:
            ready_refs, notready_refs = ray.wait(notready_refs, timeout=poll_interval)
            pbar.update(len(ready_refs))
            for ref in ready_refs:
                try:
                    output[ref2index[ref]] = ray_get(ref)
                except:
                    logger.error("ray_map failed at item index {}", ref2index[ref])
                    raise

        if auto_shutdown:
            if before_shutdown is not None:
                output = [before_shutdown(x) for x in output]
            ray_shutdown()
        return output


@require_ray
def ray_actor_map(
    actor_fns: list[Callable],
    args_lst: Sequence[Sequence],
    verbose: bool = False,
    poll_interval: float = 0.1,
    concurrent_submissions: int = 3000,
    desc: Optional[str] = None,
    postprocess: Optional[Callable[[Any], Any]] = None,
    before_shutdown: Optional[Callable[[Any], Any]] = None,
    auto_shutdown: bool = False,
):
    n_jobs = len(args_lst)
    with tqdm(total=n_jobs, desc=desc, disable=not verbose) as pbar:
        output: list = [None] * n_jobs

        notready_refs = []
        ref2index = {}
        for i, args in enumerate(args_lst):
            # submit a task and add it to not ready queue and ref2index
            ref = actor_fns[i % len(actor_fns)](*args)
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
                        output[ref2index[ref]] = ray_get(ref)
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
                    output[ref2index[ref]] = ray_get(ref)
                except:
                    logger.error(
                        "ray_actor_map failed at item index {}", ref2index[ref]
                    )
                    raise

        if postprocess is not None:
            output = [postprocess(x) for x in output]

        if auto_shutdown:
            if before_shutdown is not None:
                output = [before_shutdown(x) for x in output]
            ray_shutdown()

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
