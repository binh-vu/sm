from sm.namespaces.namespace import KnowledgeGraphNamespace, Namespace, OutOfNamespace
from sm.namespaces.utils import KGName, get_kgns
from sm.namespaces.wikidata import WikidataNamespace

__all__ = [
    "Namespace",
    "OutOfNamespace",
    "WikidataNamespace",
    "KnowledgeGraphNamespace",
    "KGName",
    "get_kgns",
]
