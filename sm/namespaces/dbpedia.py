from __future__ import annotations

from rdflib import OWL, RDF, RDFS
from sm.namespaces.namespace import (
    DefaultKnowledgeGraphNamespace,
    KnowledgeGraphNamespace,
)


class DBpediaNamespace(DefaultKnowledgeGraphNamespace):
    """Namespace for DBpedia entities and ontology"""

    entity_id: str = str(OWL.Thing)
    entity_uri: str = str(OWL.Thing)
    entity_label: str = "Thing"
    statement_uri: str = str(RDF.Statement)
    main_namespaces: list[str] = [
        "http://dbpedia.org/ontology/",
        "http://dbpedia.org/resource/",
        "http://dbpedia.org/property/",
    ]

    @classmethod
    def create(cls):
        return cls.from_prefix2ns(
            {
                "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
                "owl": "http://www.w3.org/2002/07/owl#",
                "dbo": "http://dbpedia.org/ontology/",
                "dbr": "http://dbpedia.org/resource/",
                "dbp": "http://dbpedia.org/property/",
                "dc": "http://purl.org/dc/elements/1.1/",
                "foaf": "http://xmlns.com/foaf/0.1/",
                "xsd": "http://www.w3.org/2001/XMLSchema#",
                "dul": "http://www.ontologydesignpatterns.org/ont/dul/DUL.owl#",
            }
        )
