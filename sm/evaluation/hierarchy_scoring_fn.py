import math
from typing import Dict, Callable, List, Mapping, Protocol, Iterable, Tuple
from dataclasses import dataclass
from sm.evaluation.sm_metrics import ScoringFn
from tqdm import tqdm


ItemParents = Dict[str, Iterable[str]]

MAX_ANCESTOR_DISTANCE = 5
MAX_DESCENDANT_DISTANCE = 3
INF_DISTANCE = 100


class ItemDistanceProtocol(Protocol):
    def get_distance(self, pred_item: str, target_item: str) -> int:
        """Get the distance between the predicted and target items. The distance is positive
        if the predicted item is an ancestor of the target item, and negative if the predicted
        item is a descendant of the target item.
        If the predicted item is not related to the target item, the distance can be choosed to be any number larger than MAX_ANCESTOR_DISTANCE or less than MAX_DESCENDANT_DISTANCE."""
        ...


@dataclass
class DictItemDistance:
    __slots__ = ["item2parents"]

    # mapping from the item to its parents and their distances
    # 1 is direct parent, 2 is grandparent, etc.
    item2parents: Mapping[str, Mapping[str, int]]

    def get_distance(self, pred_item: str, target_item: str) -> int:
        if pred_item == target_item:
            return 0
        if pred_item in self.item2parents[target_item]:
            return self.item2parents[target_item][pred_item]
        if target_item in self.item2parents[pred_item]:
            return -self.item2parents[pred_item][target_item]
        return INF_DISTANCE


class HierarchyScoringFn(ScoringFn):
    def __init__(
        self,
        item_distance: ItemDistanceProtocol,
    ):
        self.item_distance = item_distance

    def get_match_score(self, pred_item: str, target_item: str):
        if pred_item == target_item:
            return 1.0
        distance = self.item_distance.get_distance(pred_item, target_item)
        assert distance != 0.0
        if distance > 0:
            # pred_predicate is the ancestor of the target
            if distance > MAX_ANCESTOR_DISTANCE:
                return 0.0
            return math.pow(0.8, distance)
        if distance < 0:
            # pred_predicate is the descendant of the target
            distance = -distance
            if distance > MAX_DESCENDANT_DISTANCE:
                return 0.0
            return math.pow(0.7, distance)
        return 0.0

    @staticmethod
    def construct(
        items: List[str],
        get_item_parents: Callable[[str], Iterable[str]],
        get_item_uri: Callable[[str], str],
        verbose: bool = False,
    ):
        """Create a HierarchyScoringFn from a list of items

        Args:
            items: List of items to build the scoring function
            get_item_parents: Function that returns the parents of an item
            get_item_uri: Function that returns the URI of an item
        """
        item2parents = {item: {} for item in items}

        for item in tqdm(items, disable=not verbose):
            # a mapping of visited item to the distance that we encounter it
            visited = {}
            stack: List[Tuple[str, int]] = [
                (parent, 1) for parent in get_item_parents(item)
            ]
            while len(stack) > 0:
                node, distance = stack.pop()
                if node in visited and distance >= visited[node]:
                    # we have visited this node before and since last time we visit
                    # the previous route is shorter, so we don't need to visit it again
                    continue

                visited[node] = distance
                item2parents[item][node] = min(
                    distance, item2parents[item].get(node, float("inf"))
                )

                for parent in get_item_parents(node):
                    stack.append((parent, distance + 1))

        return HierarchyScoringFn(
            DictItemDistance(
                {
                    get_item_uri(k): {get_item_uri(k2): v2 for k2, v2 in v.items()}
                    for k, v in item2parents.items()
                }
            )
        )
