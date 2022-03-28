from __future__ import annotations
from typing import Dict, Union
from pathlib import Path
from dataclasses import dataclass
from sm.misc.deser import deserialize_yml

from sm.namespaces.prefix_index import PrefixIndex


class OutOfNamespace(Exception):
    pass


default_ns_file = Path(__file__).absolute().parent.parent / "data/namespaces.yml"


@dataclass
class Namespace:
    """A helper class for converting between absolute URI and relative URI."""

    __slots__ = ("prefix2ns", "prefix_index")

    prefix2ns: Dict[str, str]
    prefix_index: PrefixIndex

    @classmethod
    def from_file(cls, infile: Union[Path, str] = default_ns_file):
        prefix2ns = dict(deserialize_yml(infile))
        ns2prefix = {v: k for k, v in prefix2ns.items()}
        assert len(ns2prefix) == len(prefix2ns), "Duplicated namespaces"
        prefix_index = PrefixIndex.create(ns2prefix)

        return cls(prefix2ns=prefix2ns, prefix_index=prefix_index)

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

    def is_uri_in_ns(self, abs_uri: str, prefix: str):
        """Check if an absolute URI is in a namespace specified by the prefix."""
        return abs_uri.startswith(self.prefix2ns[prefix])

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
