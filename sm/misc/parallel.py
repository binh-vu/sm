from multiprocessing import Pool
from operator import itemgetter
from inspect import signature
from typing import Any, Callable, List, Optional

from loguru import logger
from tqdm import tqdm
from multiprocessing.pool import ThreadPool

Fn = Callable


class Parallel:
    def __init__(self):
        pass

    def map(
        self,
        fn: Fn,
        inputs: list,
        show_progress=False,
        progress_desc="",
        is_parallel=True,
        use_threadpool=False,
        n_processes: Optional[int] = None,
        ignore_error: bool = False,
    ) -> List[Any]:
        """Execute a map function over each input in parallel"""
        if not is_parallel:
            wrapped_fn = ParallelFnWrapper(fn, ignore_error=False).run
            return [
                wrapped_fn((0, item))[1]
                for item in tqdm(
                    inputs,
                    total=len(inputs),
                    desc=progress_desc,
                    disable=not show_progress,
                )
            ]

        if use_threadpool:
            with ThreadPool(processes=n_processes) as pool:
                iter = pool.imap_unordered(
                    ParallelFnWrapper(fn, ignore_error).run,
                    enumerate(inputs),
                )
                results = []
                for result in tqdm(
                    iter,
                    total=len(inputs),
                    desc=progress_desc,
                    disable=not show_progress,
                ):
                    results.append(result)
                results.sort(key=itemgetter(0))
        else:
            # start a pool of processes
            with Pool(processes=n_processes) as pool:
                iter = pool.imap_unordered(
                    ParallelFnWrapper(fn, ignore_error).run,
                    enumerate(inputs),
                )
                results = []
                for result in tqdm(
                    iter,
                    total=len(inputs),
                    desc=progress_desc,
                    disable=not show_progress,
                ):
                    results.append(result)
                results.sort(key=itemgetter(0))

        return [v for i, v in results]

    def foreach(
        self,
        fn: Fn,
        inputs: list,
        show_progress=False,
        progress_desc="",
        is_parallel=True,
        use_threadpool=False,
        n_processes: Optional[int] = None,
        ignore_error: bool = False,
    ) -> None:
        """Execute a map function over each input in parallel"""
        if not is_parallel:
            for item in tqdm(
                inputs,
                total=len(inputs),
                desc=progress_desc,
                disable=not show_progress,
            ):
                fn(item)
            return

        if use_threadpool:
            with ThreadPool(processes=n_processes) as pool:
                iter = pool.imap_unordered(
                    ParallelFnWrapper(fn, ignore_error).run_no_return,
                    enumerate(inputs),
                )
                results = []
                for result in tqdm(
                    iter,
                    total=len(inputs),
                    desc=progress_desc,
                    disable=not show_progress,
                ):
                    results.append(result)
                return

        # start a pool of processes
        with Pool(processes=n_processes) as pool:
            iter = pool.imap_unordered(
                ParallelFnWrapper(fn, ignore_error).run_no_return,
                enumerate(inputs),
            )
            results = []
            for result in tqdm(
                iter,
                total=len(inputs),
                desc=progress_desc,
                disable=not show_progress,
            ):
                results.append(result)
            return


class ParallelFnWrapper:
    def __init__(self, fn: Fn, ignore_error=False):
        self.fn = fn
        fn_params = signature(fn).parameters
        self.spread_fn_args = len(fn_params) > 1
        self.ignore_error = ignore_error

    def run(self, args):
        idx, r = args
        try:
            if self.spread_fn_args:
                r = self.fn(*r)
            else:
                r = self.fn(r)
            return idx, r
        except:
            logger.error(f"[Parallel] Error while process item {idx}")
            if self.ignore_error:
                return idx, None
            raise

    def run_no_return(self, args):
        idx, r = args
        try:
            if self.spread_fn_args:
                r = self.fn(*r)
            else:
                r = self.fn(r)
            return idx, None
        except:
            logger.error(f"[Parallel] Error while process item {idx}")
            if self.ignore_error:
                return idx, None
            raise
