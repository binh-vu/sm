from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from rsoup.core import ContentHierarchy
from sm.inputs.link import EntityId
from sm.namespaces.utils import KGName


@dataclass
class Context:
    page_title: Optional[str] = None
    page_url: Optional[str] = None
    entities: list[EntityId] = field(default_factory=list)
    literals: list[str | int] = field(default_factory=list)
    content_hierarchy: list[ContentHierarchy] = field(default_factory=list)

    def to_dict(self):
        return {
            "version": 3,
            "page_title": self.page_title,
            "page_url": self.page_url,
            "entities": [e.to_dict() for e in self.entities],
            "literals": self.literals,
            "content_hierarchy": [c.to_dict() for c in self.content_hierarchy],
        }

    @staticmethod
    def from_dict(obj: dict):
        version = obj.get("version")
        if version is None:
            return Context(
                page_title=obj.get("page_title"),
                page_url=obj.get("page_url"),
                entities=[EntityId(r, KGName.Wikidata)]
                if (r := obj.get("page_entity_id")) is not None
                else [],
                content_hierarchy=[
                    ContentHierarchy.from_dict(c)
                    for c in obj.get("content_hierarchy", [])
                ],
            )
        if version == 2:
            return Context(
                page_title=obj.get("page_title"),
                page_url=obj.get("page_url"),
                entities=[EntityId.from_dict(o) for o in obj["page_entities"]],
                content_hierarchy=[
                    ContentHierarchy.from_dict(c)
                    for c in obj.get("content_hierarchy", [])
                ],
            )
        if version == 3:
            return Context(
                page_title=obj.get("page_title"),
                page_url=obj.get("page_url"),
                entities=[EntityId.from_dict(o) for o in obj["entities"]],
                literals=obj["literals"],
                content_hierarchy=[
                    ContentHierarchy.from_dict(c)
                    for c in obj.get("content_hierarchy", [])
                ],
            )
        raise ValueError(f"Unknown version: {version}")

    def __getstate__(self):
        return {
            "page_title": self.page_title,
            "page_url": self.page_url,
            "entities": self.entities,
            "literals": self.literals,
            "content_hierarchy": [c.to_dict() for c in self.content_hierarchy],
        }

    def __setstate__(self, state):
        self.page_title = state["page_title"]
        self.page_url = state["page_url"]
        self.entities = state["entities"]
        self.literals = state["literals"]
        self.content_hierarchy = [
            ContentHierarchy.from_dict(c) for c in state.get("content_hierarchy", [])
        ]
