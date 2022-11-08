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


class Link:
    __slots__ = ("start", "end", "url", "entities")

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
                entities=[EntityId(id=eid, type="wikidata")]
                if (eid := obj["entity_id"]) is not None
                else [],
            )
        raise ValueError(f"Unknown version: {version}")
