from __future__ import annotations

from typing import List, Optional

from sm.namespaces.namespace import KnowledgeGraphNamespace
from sm.namespaces.utils import KGName
from sm.namespaces.wikidata import WikidataNamespace


class EntityId(str):
    """Represent an entity id in a knowledge graph. Note that identifiers in knowledge graphs are supposed to disjoint and the type is just
    to indicate explicitly which knowledge graph the entity belongs to.

    Otherwise, the following code `entities[entid]` where `entid = EntityId('Q5', WIKIDATA)` does not sound as another entity of same id but in different
    KG will return the same result.
    """

    __slots__ = ("type",)
    type: str

    def __new__(cls, id: str, type: str):
        obj = str.__new__(cls, id)
        obj.type = type
        return obj

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self,
            "type": self.type,
        }

    @staticmethod
    def from_dict(obj: dict) -> EntityId:
        return EntityId(
            id=obj["id"],
            type=obj["type"],
        )

    def __getnewargs__(self) -> tuple[str, str]:
        return str(self), self.type

    def belong_to(self, kgns: KnowledgeGraphNamespace) -> bool:
        if self.type == KGName.Wikidata:
            return isinstance(kgns, WikidataNamespace)
        raise NotImplementedError(self.type)


class EntityIdWithScore:
    """Represent an entity id with associated score"""

    __slots__ = ("id", "score")

    def __init__(self, id: EntityId, score: float) -> None:
        self.id = id
        self.score = score

    def to_dict(self) -> dict:
        return {"id": self.id.to_dict(), "score": self.score}

    @staticmethod
    def from_dict(obj: dict) -> EntityIdWithScore:
        return EntityIdWithScore(EntityId.from_dict(obj["id"]), obj["score"])


WIKIDATA_NIL_ENTITY = EntityId("Q0", KGName.Wikidata)


class Link:
    __slots__ = ("start", "end", "url", "entities")
    """Represent a link in a cell, a link may not cover the whole cell, so a cell
    may have multiple links.

    Attributes:
        start: start index of the link in the cell
        end: end index of the link in the cell
        url: url of the link, none means there is no hyperlink
        entities: entities linked by the link, each entity is from each knowledge graph.
            If entities is empty, it means the link should not link to any entity.
            If an entity of a target KG is NIL, it means the link should link to NIL entity
            because there is no corresponding entity in that knowledge graph.
    """

    def __init__(
        self, start: int, end: int, url: Optional[str], entities: List[EntityId]
    ):
        self.start = start
        self.end = end  # exclusive
        self.url = url  # url of the link, none means there is no hyperlink
        self.entities = entities

    def to_dict(self):
        return {
            "version": 2,
            "start": self.start,
            "end": self.end,
            "url": self.url,
            "entities": [e.to_dict() for e in self.entities],
        }

    @staticmethod
    def from_dict(obj: dict):
        version = obj.get("version")
        if version == 2:
            return Link(
                start=obj["start"],
                end=obj["end"],
                url=obj["url"],
                entities=[EntityId.from_dict(e) for e in obj["entities"]],
            )
        if version is None:
            return Link(
                start=obj["start"],
                end=obj["end"],
                url=obj["url"],
                entities=[EntityId(id=eid, type=KGName.Wikidata)]
                if (eid := obj["entity_id"]) is not None
                else [],
            )
        raise ValueError(f"Unknown version: {version}")

    def __eq__(self, other: Link):
        return (
            isinstance(other, Link)
            and self.start == other.start
            and self.end == other.end
            and self.url == other.url
            and self.entities == other.entities
        )
