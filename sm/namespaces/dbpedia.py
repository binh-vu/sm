from __future__ import annotations

from rdflib import RDF, RDFS
from sm.namespaces.namespace import (
    DefaultKnowledgeGraphNamespace,
    KnowledgeGraphNamespace,
)


class DBpediaNamespace(DefaultKnowledgeGraphNamespace):
    """Namespace for DBpedia entities and ontology"""

    entity_id: str = str(RDFS.Resource)
    entity_uri: str = str(RDFS.Resource)
    entity_label: str = "Resource"
    statement_uri: str = str(RDF.Statement)
    main_namespaces: list[str] = [
        "http://dbpedia.org/ontology/",
        "http://dbpedia.org/resource/",
    ]

    @classmethod
    def create(cls):
        return cls.from_prefix2ns(
            {
                "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
                "dbo": "http://dbpedia.org/ontology/",
            }
        )
