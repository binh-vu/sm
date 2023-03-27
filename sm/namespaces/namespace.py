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

    def is_uri_in_ns(self, abs_uri: str, prefix: Optional[str] = None):
        """Check if an absolute URI is in a namespace specified by the prefix."""
        if prefix is not None:
            return abs_uri.startswith(self.prefix2ns[prefix])
        return any(abs_uri.startswith(ns) for ns in self.prefix2ns.values())

    def get_resource_id(self, abs_uri: str):
        """
        Get the resource id from an absolute URI in its namespace, stripped out the namespace prefix.
        There is no guarantee that resources in different namespaces won't have the same id.

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
    """Abstract class for knowledge graph namespaces that allows to detect and convert between entity URIs and IDs"""

    @classmethod
    @abstractmethod
    def is_abs_uri_entity(cls, uri: str) -> bool:
        ...

    @classmethod
    @abstractmethod
    def get_entity_id(cls, uri: str) -> str:
        ...

    @classmethod
    @abstractmethod
    def get_entity_abs_uri(cls, iid: str) -> str:
        ...

    @abstractmethod
    def get_entity_rel_uri(self, iid: str) -> str:
        ...

    @classmethod
    @abstractmethod
    def get_prop_id(cls, uri: str) -> str:
        ...
