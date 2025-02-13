from __future__ import annotations

from curses.ascii import isdigit
from enum import Enum
from typing import Optional

from sm.namespaces.dbpedia import DBpediaNamespace
from sm.namespaces.namespace import KnowledgeGraphNamespace
from sm.namespaces.wikidata import ExtendedWikidataNamespace
from sm.typing import InternalID


class KGName(str, Enum):
    Wikidata = "wikidata"
    DBpedia = "dbpedia"
    Generic = "generic"

    def __str__(self):
        return self.value


registered_kgns: dict[str, KnowledgeGraphNamespace] = {
    KGName.Wikidata: ExtendedWikidataNamespace.create(),
    KGName.DBpedia: DBpediaNamespace.create(),
}


def get_kgns(kgname: KGName) -> KnowledgeGraphNamespace:
    if kgname in registered_kgns:
        return registered_kgns[kgname]
    raise NotImplementedError(kgname)


def register_kgns(kgname: str, kgns: KnowledgeGraphNamespace):
    global registered_kgns
    registered_kgns[kgname] = kgns


def has_kgns(kgname: str) -> bool:
    global registered_kgns
    return kgname in registered_kgns
