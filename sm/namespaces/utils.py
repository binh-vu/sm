from enum import Enum

from sm.namespaces.namespace import KnowledgeGraphNamespace
from sm.namespaces.wikidata import WikidataNamespace

registered_kgns: dict[str, KnowledgeGraphNamespace] = {}


class KGName(str, Enum):
    Wikidata = "wikidata"
    DBpedia = "dbpedia"


def get_kgns(kgname: KGName) -> KnowledgeGraphNamespace:
    if kgname == "wikidata":
        return WikidataNamespace.create()
    if kgname in registered_kgns:
        return registered_kgns[kgname]
    raise NotImplementedError(kgname)


def register_kgns(kgname: str, kgns: KnowledgeGraphNamespace):
    global registered_kgns
    registered_kgns[kgname] = kgns


def has_kgns(kgname: str) -> bool:
    global registered_kgns
    return kgname in registered_kgns
