from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Iterator, TypeVar, Generic, List, Tuple, overload, Union


T = TypeVar("T")


@dataclass
class Matrix(Generic[T]):
    """Helper class to work with 2D array with Python's object."""

    data: List[List[T]]

    @staticmethod
    def default(shp: Tuple[int, int], default: T | Callable[[], T]) -> Matrix[T]:
        if callable(default):
            return Matrix([[default() for _ in range(shp[1])] for _ in range(shp[0])])
        return Matrix([[default for _ in range(shp[1])] for _ in range(shp[0])])

    def shape(self) -> Tuple[int, int]:
        nrows = len(self.data)
        if nrows == 0:
            return 0, 0

        ncols = {len(row) for row in self.data}
        if len(ncols) > 1:
            raise ValueError("Matrix is not rectangular")
        return nrows, ncols.pop()

    @overload
    def __getitem__(self, item: int | Tuple[int, slice] | Tuple[slice, int]) -> List[T]:
        ...

    @overload
    def __getitem__(self, item: Tuple[int, int]) -> T:
        ...

    @overload
    def __getitem__(self, item: slice | Tuple[slice, slice]) -> List[List[T]]:
        ...

    def __getitem__(
        self,
        item: int
        | slice
        | Tuple[int, int]
        | Tuple[slice, slice]
        | Tuple[int, slice]
        | Tuple[slice, int],
    ) -> List[T] | List[List[T]] | T:
        if isinstance(item, (int, slice)):
            return self.data[item]
        if isinstance(item[0], slice):
            return [row[item[1]] for row in self.data[item[0]]]  # type: ignore
        return self.data[item[0]][item[1]]

    def __setitem__(self, key: Tuple[int, int], value: T):
        self.data[key[0]][key[1]] = value

    def flat_iter(self) -> Iterator[T]:
        return (item for row in self.data for item in row)

    def enumerate_flat_iter(self) -> Iterator[Tuple[int, int, T]]:
        return (
            (ri, ci, item)
            for ri, row in enumerate(self.data)
            for ci, item in enumerate(row)
        )