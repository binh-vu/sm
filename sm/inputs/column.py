from __future__ import annotations

import functools
import re
from typing import List, Optional


class Column:
    # conflict with cached_property
    # __slots__ = ("index", "name", "values")

    def __init__(self, index: int, name: Optional[str], values: List):
        """
        :param index: index of the column in the original table
        :param name: name of the column, None mean the column doesn't have any name (different from having empty name)
        :param values: values in each row
        """
        self.index = index
        self.name = name
        self.values = values

    @functools.cached_property
    def clean_name(self) -> Optional[str]:
        """Clean the name that may contain many unncessary spaces."""
        if self.name is None:
            return None

        return re.sub(r"\s+", " ", self.name).strip()

    @functools.cached_property
    def clean_multiline_name(self) -> Optional[str]:
        """Clean the name that may contain many unncessary spaces. However, this function keeps the newlines intact."""
        if self.name is None:
            return None

        key = None
        for k in ["##", "###", "#@#"]:
            if k not in self.name:
                key = k
                break
        assert key is not None, "Cannot find a key to replace newlines"
        s = re.sub(r"\n+", key, self.name)  # replace newlines with key
        s = re.sub(r"\s+", " ", s).strip()  # replace multiple spaces with one space
        s = re.sub(
            f" *{key} *", "\n", s
        )  # replace key with surrounded spaces with newline
        s = re.sub(
            f"\n+", "\n", s
        )  # replace multiple consecutive newlines with a single newline
        return s

    def __getitem__(self, item):
        return self.values[item]

    def __setitem__(self, key, value):
        self.values[key] = value

    def select_rows(self, indices: list[int]) -> Column:
        return Column(self.index, self.name, [self.values[i] for i in indices])

    def to_dict(self):
        return {"index": self.index, "name": self.name, "values": self.values}
