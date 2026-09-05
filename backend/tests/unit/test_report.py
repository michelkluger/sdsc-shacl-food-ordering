"""Error-mapping tests.

The mapping from a SHACL report to a JSON pointer is what makes a violation actionable in a
form, and it is the piece most likely to break quietly: a wrong pointer still returns a 422, it
just attaches the message to the wrong control or to nothing at all.
"""

from __future__ import annotations

from decimal import Decimal

from rdflib import Graph

from food_api.shacl.introspect import OptionTerm, PropertyConstraints
from food_api.shacl.jsonforms import FormDefinition, build_form
from food_api.shacl.report import collect_violations

FOOD = "https://sdsc.example/ns/food#"
SH_IRI = "http://www.w3.org/ns/shacl#IRI"

REPORT_PREAMBLE = """
@prefix food: <https://sdsc.example/ns/food#> .
@prefix sh:   <http://www.w3.org/ns/shacl#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
"""


def _form() -> FormDefinition:
    return build_form(
        (
            PropertyConstraints(
                path=f"{FOOD}topping",
                name="toppings",
                node_kind=SH_IRI,
                max_count=5,
                options=(
                    OptionTerm(
                        iri=f"{FOOD}chashu",
                        token="chashu",
                        label="Chashu pork",
                        surcharge=Decimal(3),
                    ),
                    OptionTerm(iri=f"{FOOD}nori", token="nori", label="Nori"),
                ),
            ),
            PropertyConstraints(
                path=f"{FOOD}spiceLevel",
                name="spiceLevel",
                max_count=1,
                min_inclusive=Decimal(0),
                max_inclusive=Decimal(5),
            ),
        ),
        base_context={"@vocab": FOOD},
        title="Test",
    )


def _report(turtle: str) -> Graph:
    graph = Graph()
    graph.parse(data=REPORT_PREAMBLE + turtle, format="turtle")
    return graph


def test_scalar_violation_points_at_its_field() -> None:
    report = _report("""
    [] a sh:ValidationResult ;
        sh:resultSeverity sh:Violation ;
        sh:sourceConstraintComponent sh:MaxInclusiveConstraintComponent ;
        sh:resultPath food:spiceLevel ;
        sh:value 9 ;
        sh:resultMessage "Spice level runs from 0 to 5." .
    """)
    (violation,) = collect_violations(report, _form(), {"spiceLevel": 9})

    assert violation.pointer == "/spiceLevel"
    assert violation.field == "spiceLevel"
    assert violation.value == 9
    assert violation.severity == "violation"
    assert violation.constraint == "MaxInclusiveConstraintComponent"


def test_array_violation_points_at_the_offending_element() -> None:
    """The message belongs on the chip the user picked, not on the whole control."""
    report = _report("""
    [] a sh:ValidationResult ;
        sh:resultSeverity sh:Violation ;
        sh:sourceConstraintComponent sh:SPARQLConstraintComponent ;
        sh:resultPath food:topping ;
        sh:value food:chashu ;
        sh:resultMessage "Chashu pork is not available with a vegan broth." .
    """)
    payload = {"toppings": ["nori", "chashu"]}
    (violation,) = collect_violations(report, _form(), payload)

    assert violation.pointer == "/toppings/1"
    assert violation.value == "chashu"


def test_iri_values_are_reported_as_the_token_the_client_sent() -> None:
    report = _report("""
    [] a sh:ValidationResult ; sh:resultSeverity sh:Violation ;
        sh:sourceConstraintComponent sh:InConstraintComponent ;
        sh:resultPath food:topping ; sh:value food:chashu ; sh:resultMessage "no" .
    """)
    (violation,) = collect_violations(report, _form(), {})
    assert violation.value == "chashu"
    assert "https://" not in str(violation.value)


def test_value_absent_from_the_array_falls_back_to_the_field() -> None:
    """A cardinality violation reports the whole property, so there is no index to point at."""
    report = _report("""
    [] a sh:ValidationResult ; sh:resultSeverity sh:Violation ;
        sh:sourceConstraintComponent sh:MaxCountConstraintComponent ;
        sh:resultPath food:topping ; sh:resultMessage "Pick at most five toppings." .
    """)
    (violation,) = collect_violations(report, _form(), {"toppings": ["nori"]})
    assert violation.pointer == "/toppings"


def test_closed_violation_names_the_unexpected_field_and_hides_the_order_iri() -> None:
    report = _report("""
    [] a sh:ValidationResult ; sh:resultSeverity sh:Violation ;
        sh:sourceConstraintComponent sh:ClosedConstraintComponent ;
        sh:resultPath food:secretDiscount ; sh:value "free" ;
        sh:resultMessage "Node <urn:food:order:abc> is closed. It cannot have value: free" .
    """)
    (violation,) = collect_violations(report, _form(), {"secretDiscount": "free"})

    assert violation.pointer == "/secretDiscount"
    assert violation.message == "'secretDiscount' is not a field of this dish's form."
    assert "urn:food:order" not in violation.message


def test_unknown_path_not_present_in_the_payload_reports_at_the_root() -> None:
    report = _report("""
    [] a sh:ValidationResult ; sh:resultSeverity sh:Violation ;
        sh:sourceConstraintComponent sh:NodeKindConstraintComponent ;
        sh:resultPath food:ghost ; sh:resultMessage "boo" .
    """)
    (violation,) = collect_violations(report, _form(), {})
    assert violation.pointer == ""
    assert violation.field is None


def test_missing_message_gets_a_readable_fallback() -> None:
    report = _report("""
    [] a sh:ValidationResult ; sh:resultSeverity sh:Violation ;
        sh:sourceConstraintComponent sh:DatatypeConstraintComponent ;
        sh:resultPath food:spiceLevel .
    """)
    (violation,) = collect_violations(report, _form(), {})
    assert violation.message == "'spiceLevel' does not satisfy the Datatype constraint."


def test_violations_are_returned_in_a_stable_order() -> None:
    """Report graphs are unordered; an unstable error list would reshuffle the UI each submit."""
    report = _report("""
    [] a sh:ValidationResult ; sh:resultSeverity sh:Violation ;
        sh:sourceConstraintComponent sh:MaxInclusiveConstraintComponent ;
        sh:resultPath food:spiceLevel ; sh:resultMessage "b" .
    [] a sh:ValidationResult ; sh:resultSeverity sh:Violation ;
        sh:sourceConstraintComponent sh:MaxCountConstraintComponent ;
        sh:resultPath food:topping ; sh:resultMessage "a" .
    """)
    form, payload = _form(), {}
    first = [violation.pointer for violation in collect_violations(report, form, payload)]
    second = [violation.pointer for violation in collect_violations(report, form, payload)]

    assert first == second == ["/spiceLevel", "/toppings"]


def test_warning_severity_is_preserved() -> None:
    report = _report("""
    [] a sh:ValidationResult ; sh:resultSeverity sh:Warning ;
        sh:sourceConstraintComponent sh:PatternConstraintComponent ;
        sh:resultPath food:spiceLevel ; sh:resultMessage "hmm" .
    """)
    (violation,) = collect_violations(report, _form(), {})
    assert violation.severity == "warning"
