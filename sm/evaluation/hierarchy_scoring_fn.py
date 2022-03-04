import math
from typing import Dict, Callable, List, Mapping, Set, Iterable, Tuple
from dataclasses import dataclass
from sm.evaluation.sm_metrics import ScoringFn
from tqdm import tqdm


ItemParents = Dict[str, Iterable[str]]


@dataclass
class HierarchyScoringFn(ScoringFn):
    # mapping from the item to its parents and their distances
    # 1 is direct parent, 2 is grandparent, etc.
    item2parents: Mapping[str, Mapping[str, int]]

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
            {
                get_item_uri(k): {get_item_uri(k2): v2 for k2, v2 in v.items()}
                for k, v in item2parents.items()
            }
        )

    def get_match_score(self, pred_item: str, target_item: str):
        if pred_item == target_item:
            return 1.0
        if pred_item in self.item2parents[target_item]:
            # pred_predicate is the parent of the target
            distance = self.item2parents[target_item][pred_item]
            if distance > 5:
                return 0.0
            return math.pow(0.8, distance)
        if target_item in self.item2parents[pred_item]:
            distance = self.item2parents[pred_item][target_item]
            if distance > 3:
                return 0.0
            return math.pow(0.7, distance)
        return 0.0
