from __future__ import annotations

from typing import Optional, cast

from sm.evaluation.sm_metrics import ScoringFn
from sm.evaluation.utils import PrecisionRecallF1


def precision_recall_f1(
    ytrue: list[Optional[str]] | list[set[str]],
    ypreds: list[Optional[str]],
    scoring_fn: Optional[ScoringFn] = None,
):
    """Calculate precision, recall, and f1. For each example, if the true label is either None or empty, it is out-of-class (e.g., dangling, nil, negative (for binary classifcation)) and the system
    should not predict anything (if the system does, it's a false positive). If the predict label is None, it means the system predicts this is out-of-class but of course it does not get any reward for
    that except for the fact that it does not get penalized for false positive.

    Difference from sklearn.metrics.precision_recall_f1_score: this function supports customizing the scoring function to calculate approximate recall.

    Args:
        ytrue: list of true labels per example. When there are more than one correct labels per example, we treat a prediction is correct if it is
            in the set of correct labels.
        ypreds: list of predicted labels per example, sorted by their likelihood in decreasing order.
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
            n_correct += max(
                scoring_fn.get_match_score(yipred, yitrue) for yitrue in ytrue[i]
            )
        else:
            assert (
                len(ytrue[i]) == 0 or yipred is None
            ), "To ensure that we don't count in case where there is no label and the system do not predict anything"

    precision = n_correct / n_predictions if n_predictions > 0 else 1.0
    recall = n_correct / n_labels if n_labels > 0 else 1.0
    f1 = (
        2 * precision * recall / (precision + recall) if precision + recall > 0 else 0.0
    )

    return PrecisionRecallF1(precision, recall, f1)
