from __future__ import annotations

import re

from rdflib import RDFS
from sm.namespaces.namespace import KnowledgeGraphNamespace, OutOfNamespace
from sm.namespaces.prefix_index import PrefixIndex


class WikidataNamespace(KnowledgeGraphNamespace):
    """Namespace for Wikidata entities and ontology.

    In Wikidata, everything is an entity (classes, properties, items, etc.). But they also have decicated namespaces for their ontology predicates (/prop/).
    So for semantic models, we use the namespace for their properties instead of treating them as entities.
    For example, we use p:P131 instead of wd:P131.
    """

    __slots__ = ("entity_prefix", "entity_ns", "property_prefix", "property_ns")

    # the root entity of Wikidata, any other class is a subclass of this
    entity_id: str = "Q35120"
    entity_uri: str = "http://www.wikidata.org/entity/Q35120"
    entity_label: str = "Entity (Q35120)"  # the label of the root entity
    # statement to represent n-ary relations
    statement_uri: str = "http://wikiba.se/ontology#Statement"
    main_namespaces: list[str] = [
        "http://www.wikidata.org/prop/",
        "http://www.wikidata.org/entity/",
    ]

    URI_RE = re.compile(
        r"^https?:\/\/www\.wikidata\.org\/(?:entity\/|prop\/|wiki\/Property:|wiki\/)([QPL]\d+)$"
    )
    IS_WIKIDATA_URI = re.compile(r"^https?:\/\/www\.wikidata\.org\/")

    @classmethod
    def create(cls):
        prefix2ns = {
            "p": "http://www.wikidata.org/prop/",
            "pq": "http://www.wikidata.org/prop/qualifier/",
            "pqn": "http://www.wikidata.org/prop/qualifier/value-normalized/",
            "pqv": "http://www.wikidata.org/prop/qualifier/value/",
            "pr": "http://www.wikidata.org/prop/reference/",
            "prn": "http://www.wikidata.org/prop/reference/value-normalized/",
            "prv": "http://www.wikidata.org/prop/reference/value/",
            "ps": "http://www.wikidata.org/prop/statement/",
            "psn": "http://www.wikidata.org/prop/statement/value-normalized/",
            "psv": "http://www.wikidata.org/prop/statement/value/",
            "wd": "http://www.wikidata.org/entity/",
            "wdata": "http://www.wikidata.org/wiki/Special:EntityData/",
            "wdno": "http://www.wikidata.org/prop/novalue/",
            "wdref": "http://www.wikidata.org/reference/",
            "wds": "http://www.wikidata.org/entity/statement/",
            "wdt": "http://www.wikidata.org/prop/direct/",
            "wdtn": "http://www.wikidata.org/prop/direct-normalized/",
            "wdv": "http://www.wikidata.org/value/",
            "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
            "wikibase": "http://wikiba.se/ontology#",
        }
        ns2prefix = {v: k for k, v in prefix2ns.items()}
        assert len(ns2prefix) == len(prefix2ns), "Duplicated namespaces"
        prefix_index = PrefixIndex.create(ns2prefix)

        return cls(prefix2ns, ns2prefix, prefix_index)

    def __init__(
        self,
        prefix2ns: dict[str, str],
        ns2prefix: dict[str, str],
        prefix_index: PrefixIndex,
    ):
        super().__init__(prefix2ns, ns2prefix, prefix_index)
        self.entity_prefix = "wd"
        self.property_prefix = "p"
        self.entity_ns = self.prefix2ns[self.entity_prefix]
        self.property_ns = self.prefix2ns[self.property_prefix]

    ###############################################################################
    # URI testing
    ###############################################################################

    @classmethod
    def is_abs_uri_statement(cls, uri: str):
        return uri == WikidataNamespace.statement_uri

    @classmethod
    def is_abs_uri_property(cls, uri: str):
        return uri.startswith(f"http://www.wikidata.org/prop/P") or uri.startswith(
            f"http://www.wikidata.org/entity/P"
        )

    @classmethod
    def is_abs_uri_qnode(cls, uri: str):
        return uri.startswith("http://www.wikidata.org/entity/Q")

    @classmethod
    def is_abs_uri_lexeme(cls, uri: str):
        return uri.startswith("http://www.wikidata.org/entity/L")

    @classmethod
    def is_abs_uri_entity(cls, uri: str):
        return uri.startswith("http://www.wikidata.org/entity/")

    ###############################################################################
    # Converting between URI and ID
    ###############################################################################

    def is_id(self, id: str):
        return (id[0] == "Q" or id[0] == "P" or id[0] == "L") and id[1:].isdigit()

    def is_uri_in_main_ns(self, uri: str) -> bool:
        return self.URI_RE.match(uri) is not None

    def uri_to_id(self, uri: str) -> str:
        m = self.URI_RE.match(uri)
        if m is None:
            raise OutOfNamespace(f"{uri} is not in wikidata namespace")
        return m.group(1)

    def id_to_uri(self, id: str):
        assert self.is_id(id), id
        if id[0] == "Q" or id[0] == "L":
            return f"{self.entity_ns}{id}"
        assert id[0] == "P"
        return f"{self.property_ns}{id}"

    def has_encrypted_name(self, uri: str):
        return self.IS_WIKIDATA_URI.match(uri) is not None


class ExtendedWikidataNamespace(WikidataNamespace):
    extra_properties = {str(RDFS.label)}

    def uri_to_id(self, uri: str) -> str:
        if uri in self.extra_properties:
            return uri
        return super().uri_to_id(uri)

    def id_to_uri(self, id: str):
        if id in self.extra_properties:
            return id
        return super().id_to_uri(id)
