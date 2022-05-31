from sm.namespaces.namespace import Namespace, OutOfNamespace
from sm.namespaces.prefix_index import PrefixIndex


class WikidataNamespace(Namespace):
    """Namespace for Wikidata entities and ontology.

    In Wikidata, everything is an entity (classes, properties, items, etc.). But they also have decicated namespaces for their ontology predicates (/prop/).
    So for semantic models, we use the namespace for their properties instead of treating them as entities.
    For example, we use p:P131 instead of wd:P131.
    """

    STATEMENT_URI = (
        "http://wikiba.se/ontology#Statement"  # statement to represent n-ary relations
    )
    DUMMY_CLASS_FOR_INVERSION_URI = "http://wikiba.se/ontology#DummyClassForInversion"

    @staticmethod
    def create():
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
            "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        }
        ns2prefix = {v: k for k, v in prefix2ns.items()}
        assert len(ns2prefix) == len(prefix2ns), "Duplicated namespaces"
        prefix_index = PrefixIndex.create(ns2prefix)

        return WikidataNamespace(prefix2ns=prefix2ns, prefix_index=prefix_index)

    ###############################################################################
    # URI testing
    ###############################################################################

    @classmethod
    def is_abs_uri_statement(cls, uri: str):
        return uri == WikidataNamespace.STATEMENT_URI

    @classmethod
    def is_abs_uri_dummy_class(cls, uri: str):
        return uri == WikidataNamespace.DUMMY_CLASS_FOR_INVERSION_URI

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

    @classmethod
    def is_valid_id(cls, id: str):
        return (id[0] == "Q" or id[0] == "P" or id[0] == "L") and id[1:].isdigit()

    @classmethod
    def get_entity_id(cls, uri: str):
        if uri.startswith("http://www.wikidata.org/entity/"):
            return uri.replace("http://www.wikidata.org/entity/", "")
        raise OutOfNamespace(f"{uri} is not in wikidata entity namespace")

    @classmethod
    def get_prop_id(cls, uri: str):
        if uri.startswith("http://www.wikidata.org/prop/"):
            # so this we can handle /prop/ and /prop/direct/
            return uri[uri.rfind("/") + 1 :]
        if uri.startswith("http://www.wikidata.org/entity/P"):
            return uri.replace("http://www.wikidata.org/entity/P", "")
        raise OutOfNamespace(f"{uri} is not in wikidata property namespace")

    @classmethod
    def get_entity_abs_uri(cls, iid: str):
        assert cls.is_valid_id(iid), iid
        return f"http://www.wikidata.org/entity/{iid}"

    @classmethod
    def get_prop_abs_uri(cls, pid: str):
        assert cls.is_valid_id(pid), pid
        return f"http://www.wikidata.org/prop/{pid}"

    @classmethod
    def get_entity_rel_uri(cls, iid: str):
        assert cls.is_valid_id(iid), iid
        return f"wd:{iid}"

    @classmethod
    def get_prop_rel_uri(cls, pid: str):
        assert cls.is_valid_id(pid), pid
        return f"p:{pid}"
