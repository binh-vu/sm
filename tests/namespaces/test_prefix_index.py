from rdflib import RDFS
from sm.namespaces.prefix_index import PrefixIndex


def test_prefix_index():
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
    }
    ns2prefix = {v: k for k, v in prefix2ns.items()}
    index = PrefixIndex.create(ns2prefix)

    assert index.get("http://www.wikidata.org/prop/P131") == "p"
    assert index.get(RDFS.label) == "rdfs", "The index works with rdflib.URIRef"

    assert index.to_dict() == {
        "http://www.wikidata.org/prop/": {
            "direct/": "wdt",
            "novalue": "wdno",
            "direct-": "wdtn",
            "stateme": {
                "nt/": {
                    "value/": "psv",
                    "value-": "psn",
                    "": "ps",
                }
            },
            "referen": {
                "ce/": {
                    "value/": "prv",
                    "value-": "prn",
                    "": "pr",
                }
            },
            "qualifi": {
                "er/": {
                    "value/": "pqv",
                    "value-": "pqn",
                    "": "pq",
                }
            },
            "": "p",
        },
        "http://www.wikidata.org/wiki/": "wdata",
        "http://www.wikidata.org/entit": {
            "y/": {
                "statement/": "wds",
                "": "wd",
            }
        },
        "http://www.w3.org/2000/01/rdf": "rdfs",
        "http://www.wikidata.org/refer": "wdref",
        "http://www.wikidata.org/value": "wdv",
    }
