from __future__ import annotations
from typing import Generic, Iterable, TypeVar, Sequence
from typing_extensions import Self


V1 = TypeVar("V1")
V2 = TypeVar("V2")


class Bijection(Generic[V1, V2]):
    def __init__(self):
        self.x2prime: dict[V1, V2] = {}
        self.prime2x: dict[V2, V1] = {}

    def size(self) -> int:
        return len(self.x2prime)

    def add(self, x: V1, xprime: V2) -> bool:
        """Add a invertible mapping between x and xprime. Return true if
        successful (even when an existing mapping exists), false if x or xprime is already mapped to another value.
        """
        if (x in self.x2prime) != (xprime in self.prime2x):
            return False

        if x in self.x2prime:
            return self.x2prime[x] == xprime

        self.x2prime[x] = xprime
        self.prime2x[xprime] = x

        return True

    def check_add(self, x: V1, xprime: V2) -> Self:
        """Add a invertible mapping between x and xprime. Return Self if
        successful or raise ValueError exception if x or xprime is already mapped to another value.
        """
        flag = self.add(x, xprime)
        if not flag:
            raise ValueError(
                f"Cannot add mapping {x} <-> {xprime} because it contradicts with existing mapping {self.x2prime.get(x, '∅')} -> {self.prime2x.get(xprime, '∅')}"
            )
        return self

    def get_x(self, xprime):
        return self.prime2x[xprime]

    def get_xprime(self, x):
        return self.x2prime[x]


class IntBijection(Generic[V1]):
    """Map from an id into an integer (started from 0)"""

    def __init__(self):
        self.data = []
        self.index: dict[V1, int] = {}

    @staticmethod
    def create(data: Iterable[V1] | Sequence[V1]) -> IntBijection[V1]:
        obj = IntBijection()
        for x in data:
            if x not in obj.index:
                obj.index[x] = len(obj.data)
                obj.data.append(x)
        return obj

    def insert(self, value: V1):
        if value not in self.index:
            self.index[value] = len(self.data)
            self.data.append(value)

    def get_x(self, xprime: int):
        return self.data[xprime]

    def get_xprime(self, x: V1):
        return self.index[x]

    def get_xprimes(self, lst: list[V1]):
        return [self.index[x] for x in lst]

    def __len__(self):
        return len(self.data)

    def iter_x(self):
        return self.index.keys()

    def iter_xprime(self):
        return self.data
