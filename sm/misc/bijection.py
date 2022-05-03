from typing import Generic, TypeVar, Dict
from typing_extensions import Self


V1 = TypeVar("V1")
V2 = TypeVar("V2")


class Bijection(Generic[V1, V2]):
    def __init__(self):
        self.x2prime: Dict[V1, V2] = {}
        self.prime2x: Dict[V2, V1] = {}

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
