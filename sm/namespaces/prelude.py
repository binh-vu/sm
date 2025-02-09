from sm.namespaces.namespace import KnowledgeGraphNamespace, Namespace, OutOfNamespace
from sm.namespaces.utils import KGName, format_label, get_kgns, has_kgns, register_kgns
from sm.namespaces.wikidata import WikidataNamespace

__all__ = [
    "Namespace",
    "OutOfNamespace",
    "WikidataNamespace",
    "KnowledgeGraphNamespace",
    "KGName",
    "get_kgns",
    "register_kgns",
    "has_kgns",
    "format_label",
]
