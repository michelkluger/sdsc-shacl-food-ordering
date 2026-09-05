"""Shape-reading tests, written against small inline Turtle documents.

Keeping the Turtle inline makes each test state exactly the modelling situation it covers,
including the ones the real dishes do not contain - an unsupported datatype, a duplicate
``sh:name``, a path the translator cannot express.
"""

from __future__ import annotations

import pytest
from rdflib import Graph

from food_api.shacl.introspect import (
    ShapeError,
    find_node_shape,
    read_properties,
)

PREAMBLE = """
@prefix food: <https://sdsc.example/ns/food#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix sh:   <http://www.w3.org/ns/shacl#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
"""


def graph_of(turtle: str) -> Graph:
    graph = Graph()
    graph.parse(data=PREAMBLE + turtle, format="turtle")
    return graph


def test_reads_a_simple_property() -> None:
    graph = graph_of("""
    food:TestShape a sh:NodeShape ;
        sh:property [
            sh:path food:spiceLevel ;
            sh:name "spiceLevel" ;
            rdfs:label "Spice level" ;
            sh:description "0 to 5." ;
            sh:datatype xsd:integer ;
            sh:minCount 1 ; sh:maxCount 1 ;
            sh:minInclusive 0 ; sh:maxInclusive 5 ;
            sh:defaultValue 1 ;
            sh:message "Spice level runs from 0 to 5." ;
        ] .
    """)
    (prop,) = read_properties(graph, find_node_shape(graph))

    assert prop.name == "spiceLevel"
    assert prop.label == "Spice level"
    assert prop.is_required
    assert not prop.is_multi_valued
    assert (prop.min_inclusive, prop.max_inclusive) == (0, 5)
    assert prop.default == 1
    assert prop.message == "Spice level runs from 0 to 5."


def test_sh_in_options_are_labelled_from_the_vocabulary() -> None:
    graph = graph_of("""
    food:tonkotsu rdfs:label "Tonkotsu (pork)"@en ; food:surcharge 2.0 ;
        food:containsAllergen "pork" ; food:excludedByDiet "vegan" .
    food:shio rdfs:label "Shio (salt)"@en .
    food:TestShape a sh:NodeShape ;
        sh:property [
            sh:path food:broth ; sh:name "broth" ; sh:nodeKind sh:IRI ;
            sh:minCount 1 ; sh:maxCount 1 ;
            sh:in ( food:tonkotsu food:shio ) ;
        ] .
    """)
    (prop,) = read_properties(graph, find_node_shape(graph))

    assert [option.token for option in prop.options] == ["tonkotsu", "shio"]
    assert prop.options[0].label == "Tonkotsu (pork)"
    assert prop.options[0].surcharge == 2
    assert prop.options[0].excluded_by_diet == ("vegan",)
    # An option with no annotations must still be usable, not skipped.
    assert prop.options[1].surcharge == 0


def test_sh_in_preserves_list_order() -> None:
    """RDF lists are ordered, and a form's options must appear in the order they were written."""
    graph = graph_of("""
    food:TestShape a sh:NodeShape ;
        sh:property [
            sh:path food:size ; sh:name "size" ; sh:nodeKind sh:IRI ; sh:maxCount 1 ;
            sh:in ( food:XL food:M food:L ) ;
        ] .
    """)
    (prop,) = read_properties(graph, find_node_shape(graph))
    assert [option.token for option in prop.options] == ["XL", "M", "L"]


def test_option_with_no_label_falls_back_to_its_token() -> None:
    graph = graph_of("""
    food:TestShape a sh:NodeShape ;
        sh:property [
            sh:path food:size ; sh:name "size" ; sh:maxCount 1 ; sh:in ( food:mystery ) ;
        ] .
    """)
    (prop,) = read_properties(graph, find_node_shape(graph))
    assert prop.options[0].label == "mystery"


def test_properties_are_ordered_by_group_then_order() -> None:
    graph = graph_of("""
    food:First  a sh:PropertyGroup ; rdfs:label "First"  ; sh:order 1 .
    food:Second a sh:PropertyGroup ; rdfs:label "Second" ; sh:order 2 .
    food:TestShape a sh:NodeShape ;
        sh:property [ sh:path food:c ; sh:name "c" ; sh:group food:Second ; sh:order 1 ] ;
        sh:property [ sh:path food:b ; sh:name "b" ; sh:group food:First  ; sh:order 2 ] ;
        sh:property [ sh:path food:a ; sh:name "a" ; sh:group food:First  ; sh:order 1 ] .
    """)
    properties = read_properties(graph, find_node_shape(graph))
    assert [prop.name for prop in properties] == ["a", "b", "c"]


def test_properties_with_no_order_sort_last_and_stably() -> None:
    graph = graph_of("""
    food:TestShape a sh:NodeShape ;
        sh:property [ sh:path food:z ; sh:name "z" ] ;
        sh:property [ sh:path food:a ; sh:name "a" ] ;
        sh:property [ sh:path food:m ; sh:name "m" ; sh:order 1 ] .
    """)
    properties = read_properties(graph, find_node_shape(graph))
    assert [prop.name for prop in properties] == ["m", "a", "z"]


def test_name_falls_back_to_the_path_local_name() -> None:
    graph = graph_of("""
    food:TestShape a sh:NodeShape ;
        sh:property [ sh:path food:broth ; sh:maxCount 1 ] .
    """)
    (prop,) = read_properties(graph, find_node_shape(graph))
    assert prop.name == "broth"


def test_property_shapes_reached_by_iri_are_read_like_inline_ones() -> None:
    """Reuse via `sh:property food:Shared` must be indistinguishable from writing it inline."""
    graph = graph_of("""
    food:SharedQuantity a sh:PropertyShape ;
        sh:path food:quantity ; sh:name "quantity" ; sh:datatype xsd:integer ;
        sh:minCount 1 ; sh:maxCount 1 .
    food:TestShape a sh:NodeShape ;
        sh:property food:SharedQuantity ;
        sh:property [ sh:path food:size ; sh:name "size" ; sh:maxCount 1 ] .
    """)
    properties = read_properties(graph, find_node_shape(graph))
    assert {prop.name for prop in properties} == {"quantity", "size"}


def test_duplicate_names_are_rejected() -> None:
    """Two fields claiming one JSON key would silently overwrite each other in the form."""
    graph = graph_of("""
    food:TestShape a sh:NodeShape ;
        sh:property [ sh:path food:a ; sh:name "clash" ] ;
        sh:property [ sh:path food:b ; sh:name "clash" ] .
    """)
    with pytest.raises(ShapeError, match="clash"):
        read_properties(graph, find_node_shape(graph))


def test_unsupported_datatype_is_rejected_loudly() -> None:
    graph = graph_of("""
    food:TestShape a sh:NodeShape ;
        sh:property [ sh:path food:blob ; sh:name "blob" ; sh:datatype xsd:hexBinary ] .
    """)
    with pytest.raises(ShapeError, match="unsupported datatype"):
        read_properties(graph, find_node_shape(graph))


def test_non_iri_path_is_rejected() -> None:
    """Sequence paths are legal SHACL but have no flat JSON equivalent, so say so."""
    graph = graph_of("""
    food:TestShape a sh:NodeShape ;
        sh:property [ sh:path ( food:a food:b ) ; sh:name "nested" ] .
    """)
    with pytest.raises(ShapeError, match="sh:path"):
        read_properties(graph, find_node_shape(graph))


def test_missing_node_shape_is_rejected() -> None:
    with pytest.raises(ShapeError, match="No sh:NodeShape"):
        find_node_shape(graph_of("food:Nothing a rdfs:Class ."))


def test_two_node_shapes_are_rejected() -> None:
    graph = graph_of("""
    food:One a sh:NodeShape ; sh:property [ sh:path food:a ; sh:name "a" ] .
    food:Two a sh:NodeShape ; sh:property [ sh:path food:b ; sh:name "b" ] .
    """)
    with pytest.raises(ShapeError, match="exactly one"):
        find_node_shape(graph)
