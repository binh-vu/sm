from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

import serde.yaml
from sm.namespaces.prefix_index import PrefixIndex


class OutOfNamespace(Exception):
    pass


default_ns_file = Path(__file__).absolute().parent.parent / "data/namespaces.yml"


class Namespace:
    """A helper class for converting between absolute URI and relative URI."""

    __slots__ = ("prefix2ns", "ns2prefix", "prefix_index")

    def __init__(
        self,
        prefix2ns: dict[str, str],
        ns2prefix: dict[str, str],
        prefix_index: PrefixIndex,
    ):
        self.prefix2ns = prefix2ns
        self.ns2prefix = ns2prefix
        self.prefix_index = prefix_index

    @classmethod
    def from_file(cls, infile: Path | str = default_ns_file):
        prefix2ns = dict(serde.yaml.deser(infile))
        ns2prefix = {v: k for k, v in prefix2ns.items()}
        assert len(ns2prefix) == len(prefix2ns), "Duplicated namespaces"
        prefix_index = PrefixIndex.create(ns2prefix)

        return cls(prefix2ns, ns2prefix, prefix_index)

    @classmethod
    def from_prefix2ns(cls, prefix2ns: dict[str, str]):
        ns2prefix = {v: k for k, v in prefix2ns.items()}
        assert len(ns2prefix) == len(prefix2ns), "Duplicated namespaces"
        prefix_index = PrefixIndex.create(ns2prefix)

        return cls(prefix2ns, ns2prefix, prefix_index)

    def get_abs_uri(self, rel_uri: str):
        """Get absolute URI from relative URI."""
        prefix, name = rel_uri.split(":", 2)
        return self.prefix2ns[prefix] + name

    def get_rel_uri(self, abs_uri: str):
        """Get relative URI from absolute URI."""
        prefix = self.prefix_index.get(abs_uri)
        if prefix is None:
            raise OutOfNamespace(
                f"Cannot simply the uri `{abs_uri}` as its namespace is not defined"
            )

        return f"{prefix}:{abs_uri.replace(self.prefix2ns[prefix], '')}"

    def is_rel_uri(self, uri: str):
        """Check if an URI is relative."""
        return uri.count(":") == 1

    @classmethod
    def is_uri(cls, uri: str):
        """Check if an URI is absolute."""
        return uri.startswith("http://") or uri.startswith("https://")

    def is_uri_in_ns(self, abs_uri: str, prefix: Optional[str] = None):
        """Check if an absolute URI is in a namespace specified by the prefix."""
        if prefix is not None:
            return abs_uri.startswith(self.prefix2ns[prefix])
        return any(abs_uri.startswith(ns) for ns in self.prefix2ns.values())

    def get_local_name(self, abs_uri: str):
        """
        Get the local name from an absolute URI in its namespace, stripped out the namespace prefix.
        There is no guarantee that resources in different namespaces won't have the same local name.

        Examples:
        - http://www.wikidata.org/entity/Q512 -> Q512
        - http://dbpedia.org/resource/Berlin -> Berlin
        """
        prefix = self.prefix_index.get(abs_uri)
        if prefix is None:
            raise OutOfNamespace(
                f"Cannot get resource id of the uri `{abs_uri}` as its namespace is not defined"
            )
        return abs_uri.replace(self.prefix2ns[prefix], "")

    def is_compatible(self, ns: Namespace) -> bool:
        """Test if prefixes of two namespaces are the same"""
        return all(
            self.prefix2ns[prefix] == ns.prefix2ns[prefix]
            for prefix in set(self.prefix2ns.keys()).intersection(ns.prefix2ns.keys())
        )


class KnowledgeGraphNamespace(ABC, Namespace):
    """Abstract class for knowledge graph namespaces that allows to detect and convert between entity URIs and IDs.
    In Wikidata, IDs are local names. To generalize this across multiple namespaces, we can treat IDs as relative URIs.
    """

    @property
    @abstractmethod
    def entity_id(self) -> str:
        """ID of the entity class, which all entities are instance of"""
        ...

    @property
    @abstractmethod
    def entity_uri(self) -> str:
        """URI of the entity class, which all entities are instance of"""
        ...

    @property
    @abstractmethod
    def entity_label(self) -> str:
        """Label of the entity class, which all entities are instance of"""
        ...

    @property
    @abstractmethod
    def statement_uri(self) -> str:
        """URI of a special class (Statement) that is used to represent n-ary relationship."""
        ...

    @property
    @abstractmethod
    def main_namespaces(self) -> list[str]:
        """Get a list of main namespaces of the KG that contains entities/properties/classes. URIs in these
        main namespaces should have equivalent IDs."""
        ...

    @abstractmethod
    def is_id(self, uri_or_id: str) -> bool:
        """Test if the input string is an ID in this namespace"""
        ...

    def is_uri_in_main_ns(self, uri: str) -> bool:
        """Test if an URI has an equivalent ID in the main namespaces. For example:
        QXXX and PXXX are IDs in Wikidata namespace, but wikibase:Statement isn't.

        This function can be used to determine if an URI is in the database or not.
        """
        return any(uri.startswith(ns) for ns in self.main_namespaces)

    @abstractmethod
    def uri_to_id(self, uri: str) -> str:
        """Convert an URI to an ID in this namespace"""
        ...

    @abstractmethod
    def id_to_uri(self, id: str) -> str:
        """Convert ID to URI"""
        ...

    @abstractmethod
    def has_encrypted_name(self, uri: str):
        """Test if a URI has encrypted name such as QXXX so that we can add label to make it readable."""
        ...


class DefaultKnowledgeGraphNamespace(KnowledgeGraphNamespace):
    """This is KG namespace for RDF world, we do not have ID and everything
    is identified by URI."""

    def is_id(self, uri_or_id: str) -> bool:
        return True

    def uri_to_id(self, uri: str) -> str:
        return uri

    def id_to_uri(self, id: str) -> str:
        return id

    def has_encrypted_name(self, uri: str):
        return False


class ChainedKnowledgeGraphNamespace(KnowledgeGraphNamespace):
    def __init__(self, ns1: KnowledgeGraphNamespace, ns2: KnowledgeGraphNamespace):
        self.ns1 = ns1
        self.ns2 = ns2

    @property
    def entity_id(self):
        return self.ns2.entity_id

    @property
    def entity_uri(self):
        return self.ns2.entity_uri

    @property
    def entity_label(self):
        return self.ns2.entity_label

    @property
    def statement_uri(self):
        return self.ns2.statement_uri

    @property
    def main_namespaces(self):
        return self.ns1.main_namespaces + self.ns2.main_namespaces

    def is_id(self, uri_or_id: str) -> bool:
        return self.ns1.is_id(uri_or_id) or self.ns2.is_id(uri_or_id)

    def is_uri_in_main_ns(self, uri: str) -> bool:
        return self.ns1.is_uri_in_main_ns(uri) or self.ns2.is_uri_in_main_ns(uri)

    def uri_to_id(self, uri: str) -> str:
        if self.ns1.is_uri_in_main_ns(uri):
            return self.ns1.uri_to_id(uri)
        return self.ns2.uri_to_id(uri)

    def id_to_uri(self, id: str) -> str:
        if self.ns1.is_id(id):
            return self.ns1.id_to_uri(id)
        return self.ns2.id_to_uri(id)
