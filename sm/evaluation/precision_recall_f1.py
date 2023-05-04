from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, Sequence, cast

from sm.evaluation.sm_metrics import ScoringFn


def precision_recall_f1(
    ytrue: list[Optional[str]] | list[set[str]],
    ypreds: list[Optional[str]],
    scoring_fn: Optional[ScoringFn] = None,
):
    """Calculate precision, recall, and f1

    Args:
        ytrue: list of true labels per example. When there are more than one correct labels per example, we treat a prediction is correct if it is
            in the set of correct labels.
        ypreds: list of predicted labels per example, sorted by their likelihood in decreasing order.
        k: number of predicted labels to consider. If None, we use all predicted labels (i.e., recall@all).
        scoring_fn: the function telling how well a prediction matches a true label. Exact matching is used by default, but HierachicalScoringFn (in SemTab)
            can be used as well to calculate approximate recall at k.
    """
    if len(ytrue) == 0:
        return PrecisionRecallF1(0.0, 0.0, 0.0)

    if not isinstance(ytrue[0], (set, list, tuple)):
        ytrue = [{y} if y is not None else set() for y in cast(list[str], ytrue)]
    else:
        ytrue = cast(list[set[str]], ytrue)

    if scoring_fn is None:
        scoring_fn = ScoringFn()

    n_correct = 0
    n_predictions = sum(int(p is not None) for p in ypreds)
    n_labels = sum(int(len(y) > 0) for y in ytrue)

    for i in range(len(ytrue)):
        yipred = ypreds[i]

        if len(ytrue[i]) > 0 and yipred is not None:
            # no correct label
            score = max(
                scoring_fn.get_match_score(yipred, yitrue) for yitrue in ytrue[i]
            )
            if score > 0:
                n_correct += 1
        else:
            assert (
                yipred is not None
            ), "To ensure that we don't count in case where there is no label and the system do not predict anything"

    precision = n_correct / n_predictions if n_predictions > 0 else 1.0
    recall = n_correct / n_labels if n_labels > 0 else 1.0
    f1 = (
        2 * precision * recall / (precision + recall) if precision + recall > 0 else 0.0
    )

    return PrecisionRecallF1(precision, recall, f1)
