"""Language negotiation and selection.

Two separate concerns are tested here: choosing *which* language to serve (``api/language.py``)
and picking the right literal once chosen (``introspect.select_literal``). The second is the one
that makes partial translation safe, so it gets the most attention.
"""

from __future__ import annotations

import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import RDFS, SH

from food_api.api.language import negotiate, parse_accept_language
from food_api.shacl.introspect import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, select_literal

FOOD = "https://sdsc.example/ns/food#"


def graph_of(turtle: str) -> Graph:
    graph = Graph()
    graph.parse(
        data="@prefix food: <https://sdsc.example/ns/food#> .\n"
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
        "@prefix sh: <http://www.w3.org/ns/shacl#> .\n" + turtle,
        format="turtle",
    )
    return graph


class TestSupportedLanguages:
    def test_covers_every_swiss_national_language_plus_english(self) -> None:
        assert set(SUPPORTED_LANGUAGES) == {"en", "de", "fr", "it", "rm"}

    def test_romansh_is_included(self) -> None:
        """The one most often quietly dropped. Its absence should be a decision, not a default."""
        assert "rm" in SUPPORTED_LANGUAGES

    def test_default_is_supported(self) -> None:
        assert DEFAULT_LANGUAGE in SUPPORTED_LANGUAGES


class TestSelectLiteral:
    @pytest.fixture
    def graph(self) -> Graph:
        return graph_of("""
        food:term rdfs:label "Broth"@en, "Brühe"@de, "Bouillon"@fr, "Brodo"@it, "Bragl"@rm .
        food:untagged rdfs:label "Nori" .
        food:partial rdfs:label "Menma"@en, "Menma (Bambus)"@de .
        food:none rdfs:comment "no label here" .
        """)

    @pytest.mark.parametrize(
        ("language", "expected"),
        [("en", "Broth"), ("de", "Brühe"), ("fr", "Bouillon"), ("it", "Brodo"), ("rm", "Bragl")],
    )
    def test_selects_the_requested_language(
        self, graph: Graph, language: str, expected: str
    ) -> None:
        assert select_literal(graph, URIRef(f"{FOOD}term"), RDFS.label, language) == expected

    def test_region_subtag_matches_the_base_language(self, graph: Graph) -> None:
        """`de-CH` is the common Swiss case and must not fall through to English."""
        assert select_literal(graph, URIRef(f"{FOOD}term"), RDFS.label, "de-CH") == "Brühe"

    def test_untagged_literal_serves_every_language(self, graph: Graph) -> None:
        """This is what lets the vocabulary translate only what differs.

        "Nori" is called Nori in all five languages, so it carries one untagged label rather
        than five identical ones. Every language must still resolve it.
        """
        for language in SUPPORTED_LANGUAGES:
            assert select_literal(graph, URIRef(f"{FOOD}untagged"), RDFS.label, language) == "Nori"

    def test_partial_translation_falls_back_to_english(self, graph: Graph) -> None:
        assert select_literal(graph, URIRef(f"{FOOD}partial"), RDFS.label, "it") == "Menma"

    def test_translated_language_still_wins_over_english(self, graph: Graph) -> None:
        assert select_literal(graph, URIRef(f"{FOOD}partial"), RDFS.label, "de") == "Menma (Bambus)"

    def test_missing_predicate_returns_none(self, graph: Graph) -> None:
        assert select_literal(graph, URIRef(f"{FOOD}none"), RDFS.label, "en") is None

    def test_unknown_subject_returns_none(self, graph: Graph) -> None:
        assert select_literal(graph, URIRef(f"{FOOD}ghost"), RDFS.label, "en") is None

    def test_selects_messages_as_well_as_labels(self) -> None:
        graph = graph_of("""
        food:shape sh:message "Pick one."@en, "Wähle eines."@de .
        """)
        assert select_literal(graph, URIRef(f"{FOOD}shape"), SH.message, "de") == "Wähle eines."


class TestParseAcceptLanguage:
    def test_empty_header_yields_nothing(self) -> None:
        assert parse_accept_language(None) == []
        assert parse_accept_language("") == []

    def test_orders_by_quality(self) -> None:
        parsed = parse_accept_language("en;q=0.5, de;q=0.9, fr;q=0.1")
        assert [tag for tag, _ in parsed] == ["de", "en", "fr"]

    def test_equal_qualities_keep_their_written_order(self) -> None:
        """Browsers express preference by order when they omit q values."""
        parsed = parse_accept_language("it, de, fr")
        assert [tag for tag, _ in parsed] == ["it", "de", "fr"]

    def test_malformed_quality_is_tolerated(self) -> None:
        """A bad header from one browser must degrade, not fail the request."""
        assert [tag for tag, _ in parse_accept_language("de;q=banana")] == ["de"]


class TestNegotiate:
    def test_no_header_gives_the_default(self) -> None:
        assert negotiate(None) == DEFAULT_LANGUAGE

    @pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)
    def test_every_supported_language_can_be_asked_for(self, language: str) -> None:
        assert negotiate(f"{language};q=1.0") == language

    def test_swiss_regional_tags_resolve(self) -> None:
        assert negotiate("de-CH,de;q=0.9") == "de"
        assert negotiate("fr-CH") == "fr"
        assert negotiate("it-CH") == "it"

    def test_unsupported_language_falls_through_to_a_supported_one(self) -> None:
        assert negotiate("es-ES,es;q=0.9,fr;q=0.8") == "fr"

    def test_entirely_unsupported_header_gives_the_default(self) -> None:
        """Asking for Spanish is not a client error worth a 400; it is just not on the menu."""
        assert negotiate("es-ES,es;q=0.9") == DEFAULT_LANGUAGE

    def test_wildcard_gives_the_default(self) -> None:
        assert negotiate("*") == DEFAULT_LANGUAGE

    def test_explicit_override_beats_the_header(self) -> None:
        """Clicking the language switcher must not be overridden by browser configuration."""
        assert negotiate("de,de-CH;q=0.9", override="rm") == "rm"

    def test_unsupported_override_falls_back_to_the_header(self) -> None:
        assert negotiate("it", override="es") == "it"

    def test_override_accepts_a_region_subtag(self) -> None:
        assert negotiate(None, override="fr-CH") == "fr"

    def test_override_is_case_insensitive(self) -> None:
        assert negotiate(None, override="DE") == "de"
