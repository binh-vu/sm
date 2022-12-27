from __future__ import annotations
from typing import List, Optional


class EntityId(str):
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


WIKIDATA = "wikidata"
WIKIDATA_NIL_ENTITY = EntityId("Q0", WIKIDATA)


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
                entities=[EntityId(id=eid, type=WIKIDATA)]
                if (eid := obj["entity_id"]) is not None
                else [],
            )
        raise ValueError(f"Unknown version: {version}")
