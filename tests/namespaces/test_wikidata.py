from sm.namespaces.wikidata import WikidataNamespace


def test_wikidata_namespace():
    kgns = WikidataNamespace.create()

    for uri, id in [
        ("http://www.wikidata.org/entity/Q5", "Q5"),
        ("https://www.wikidata.org/entity/Q5", "Q5"),
        ("http://www.wikidata.org/wiki/Q5", "Q5"),
        ("https://www.wikidata.org/wiki/Q5", "Q5"),
        ("http://www.wikidata.org/prop/P105", "P105"),
        ("https://www.wikidata.org/wiki/Property:P105", "P105"),
    ]:
        assert kgns.is_uri_in_main_ns(uri), uri
        assert kgns.uri_to_id(uri) == id

    for uri in [
        "https://www.wikidata.org/wikiProperty:P105",
    ]:
        assert not kgns.is_uri_in_main_ns(uri)
