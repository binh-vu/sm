from sm.namespaces.namespace import (
    DefaultKnowledgeGraphNamespace,
    KnowledgeGraphNamespace,
    Namespace,
    OutOfNamespace,
)
from sm.namespaces.utils import KGName, get_kgns, has_kgns, register_kgns
from sm.namespaces.wikidata import WikidataNamespace

__all__ = [
    "Namespace",
    "OutOfNamespace",
    "WikidataNamespace",
    "KnowledgeGraphNamespace",
    "DefaultKnowledgeGraphNamespace",
    "KGName",
    "get_kgns",
    "register_kgns",
    "has_kgns",
]
