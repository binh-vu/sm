from enum import Enum

from sm.namespaces.namespace import KnowledgeGraphNamespace
from sm.namespaces.wikidata import WikidataNamespace


class KGName(str, Enum):
    Wikidata = "wikidata"
    DBpedia = "dbpedia"


def get_kgns(kgname: KGName) -> KnowledgeGraphNamespace:
    if kgname == "wikidata":
        return WikidataNamespace.create()
    raise NotImplementedError(kgname)
