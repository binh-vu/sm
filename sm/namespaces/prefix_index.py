from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from typing import List, Optional, Tuple, Union


class PrefixIndex:
    """Namespace indexing so we can quickly get prefix of a URI."""

    __slots__ = ("index", "start", "end")

    def __init__(
        self, index: dict[str, PrefixIndex | str], start: int, end: int
    ) -> None:
        self.index = index
        self.start = start
        self.end = end

    @staticmethod
    def create(ns2prefix: Mapping[str, str]):
        sorted_ns = sorted(ns2prefix.keys(), key=lambda x: len(x), reverse=True)
        if len(sorted_ns) == 0:
            raise Exception("No namespace provided")

        return PrefixIndex._create(ns2prefix, sorted_ns, 0)

    @staticmethod
    def _create(ns2prefix: Mapping[str, str], nses: List[str], start: int):
        shortest_ns = nses[-1]
        index = PrefixIndex({}, start, len(shortest_ns))

        if index.start == index.end:
            # we have an empty key, it must have more than one element because of the previous call
            index.index[""] = ns2prefix[nses[-1]]
            subindex = PrefixIndex._create(ns2prefix, nses[:-1], index.end)
            for key, node in subindex.index.items():
                index.index[key] = node
            return index

        tmp = defaultdict(list)
        for ns in nses:
            key = ns[index.start : index.end]
            tmp[key].append(ns)

        for key, lst_ns in tmp.items():
            if len(lst_ns) == 1:
                index.index[key] = ns2prefix[lst_ns[0]]
            else:
                index.index[key] = PrefixIndex._create(ns2prefix, lst_ns, index.end)
        return index

    def get(self, uri: str) -> Optional[str]:
        """Get prefix of an uri. Return None if it is not found"""
        key = uri[self.start : self.end]
        if key in self.index:
            value = self.index[key]
            if isinstance(value, PrefixIndex):
                return value.get(uri)
            return value

        if "" in self.index:
            return self.index[""]  # type: ignore

        return None

    def __str__(self):
        """Readable version of the index"""
        stack: List[Tuple[int, str, Union[str, PrefixIndex]]] = list(
            reversed([(0, k, v) for k, v in self.index.items()])
        )
        out = []

        while len(stack) > 0:
            depth, key, value = stack.pop()
            indent = "    " * depth
            if isinstance(value, str):
                out.append(indent + "`" + key + "`: " + value + "\n")
            else:
                out.append(indent + "`" + key + "`:" + "\n")
                for k, v in value.index.items():
                    stack.append((depth + 1, k, v))

        return "".join(out)

    def to_dict(self):
        return {
            k: v.to_dict() if isinstance(v, PrefixIndex) else v
            for k, v in self.index.items()
        }
