from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence


class PrecisionRecallF1Protocol(Protocol):
    @property
    def precision(self) -> float:
        ...

    @property
    def recall(self) -> float:
        ...

    @property
    def f1(self) -> float:
        ...


@dataclass
class PrecisionRecallF1:
    precision: float
    recall: float
    f1: float

    @staticmethod
    def avg(lst: Sequence[PrecisionRecallF1Protocol]) -> PrecisionRecallF1:
        n = len(lst)
        if n == 0:
            raise ValueError(
                "Cannot compute average precision-recall-f1 of an empty list"
            )

        precision = sum([x.precision for x in lst]) / n
        recall = sum([x.recall for x in lst]) / n
        f1 = sum([x.f1 for x in lst]) / n
        return PrecisionRecallF1(precision, recall, f1)

    def iter_prf(self):
        return [
            ("precision", self.precision),
            ("recall", self.recall),
            ("f1", self.f1),
        ]


@dataclass
class PrecisionRecallF1Support(PrecisionRecallF1):
    support: int  # the number of examples used to compute this metric
