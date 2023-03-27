from __future__ import annotations
from typing import Protocol, Sequence, cast, Optional
from dataclasses import dataclass

from sm.evaluation.sm_metrics import ScoringFn


def recall_at_k(
    ytrue: list[str] | list[set[str]],
    ypreds: list[list[str]],
    k: Optional[int | Sequence[Optional[int]]],
    scoring_fn: Optional[ScoringFn] = None,
):
    """Calculate recall@k

    Args:
        ytrue: list of true labels per example. When there are more than one correct labels per example, we treat a prediction is correct if it is
            in the set of correct labels.
        ypreds: list of predicted labels per example, sorted by their likelihood in decreasing order.
        k: number of predicted labels to consider. If None, we use all predicted labels (i.e., recall@all).
        scoring_fn: the function telling how well a prediction matches a true label. Exact matching is used by default, but HierachicalScoringFn (in SemTab)
            can be used as well to calculate approximate recall at k.
    """
    name2k = norm_k("recall", k)
    metrics = {name: 0.0 for name in name2k}

    if len(ytrue) == 0:
        return metrics

    if isinstance(ytrue[0], str):
        ytrue = [{y} for y in cast(list[str], ytrue)]
    else:
        ytrue = cast(list[set[str]], ytrue)

    if scoring_fn is None:
        for i in range(len(ytrue)):
            for name, ki in name2k.items():
                yipreds = ypreds[i] if ki is None else ypreds[i][:ki]
                if len(ytrue[i].intersection(yipreds)) > 0:
                    metrics[name] += 1.0
    else:
        for i in range(len(ytrue)):
            for name, ki in name2k.items():
                yipreds = ypreds[i] if ki is None else ypreds[i][:ki]
                if len(yipreds) + len(ytrue[i]) == 0:
                    # both are empty, we give it a perfect score
                    metrics[name] += 1.0
                elif len(yipreds) == 0 or len(ytrue[i]) == 0:
                    continue

                metrics[name] += max(
                    scoring_fn.get_match_score(pc, gc)
                    for gc in ytrue[i]
                    for pc in yipreds
                )

    if len(ytrue) > 0:
        for name in name2k:
            metrics[name] = metrics[name] * 100 / len(ytrue)

    return metrics


def norm_k(
    metric_name: str, k: Optional[int | Sequence[Optional[int]]] = None
) -> dict[str, Optional[int]]:
    if k is None or isinstance(k, int):
        k = [k]
    out = {}
    for i in k:
        if i is None:
            out[f"{metric_name}@all"] = None
        else:
            out[f"{metric_name}@{i}"] = i
    return out
