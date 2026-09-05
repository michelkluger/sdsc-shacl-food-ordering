"""Translator tests.

These build ``PropertyConstraints`` directly rather than going through a graph, so a failure
points at the translation rule and not at the Turtle. Shape-reading itself is covered in
``test_introspect.py``.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from rdflib.namespace import XSD

from food_api.shacl.introspect import OptionTerm, PropertyConstraints, PropertyGroup
from food_api.shacl.jsonforms import FormDefinition, build_form

SH_IRI = "http://www.w3.org/ns/shacl#IRI"
FOOD = "https://sdsc.example/ns/food#"


def _build(*properties: PropertyConstraints) -> FormDefinition:
    return build_form(properties, base_context={"@vocab": FOOD}, title="Test dish")


def _option(token: str, label: str, surcharge: str = "0") -> OptionTerm:
    return OptionTerm(iri=f"{FOOD}{token}", token=token, label=label, surcharge=Decimal(surcharge))


def test_required_scalar_becomes_a_required_property() -> None:
    form = _build(
        PropertyConstraints(
            path=f"{FOOD}customerName",
            name="customerName",
            datatype=str(XSD.string),
            min_count=1,
            max_count=1,
            min_length=2,
        )
    )
    assert form.schema["required"] == ["customerName"]
    assert form.schema["properties"]["customerName"]["type"] == "string"
    assert form.schema["properties"]["customerName"]["minLength"] == 2


def test_max_count_above_one_produces_an_array_with_bounds() -> None:
    form = _build(
        PropertyConstraints(
            path=f"{FOOD}topping",
            name="toppings",
            node_kind=SH_IRI,
            max_count=5,
            options=(_option("nori", "Nori"), _option("corn", "Sweetcorn")),
        )
    )
    schema = form.schema["properties"]["toppings"]
    assert schema["type"] == "array"
    assert schema["maxItems"] == 5
    assert schema["uniqueItems"] is True
    assert schema["items"]["oneOf"] == [
        {"const": "nori", "title": "Nori"},
        {"const": "corn", "title": "Sweetcorn"},
    ]


def test_absent_max_count_is_treated_as_unbounded_array() -> None:
    """A property shape with no sh:maxCount permits many values, so JSON must model a list."""
    form = _build(PropertyConstraints(path=f"{FOOD}tag", name="tags", datatype=str(XSD.string)))
    assert form.schema["properties"]["tags"]["type"] == "array"
    assert "maxItems" not in form.schema["properties"]["tags"]


def test_min_count_above_one_becomes_min_items() -> None:
    form = _build(
        PropertyConstraints(
            path=f"{FOOD}meat",
            name="meats",
            node_kind=SH_IRI,
            min_count=2,
            max_count=3,
            options=(_option("kebab", "Kebab"),),
        )
    )
    schema = form.schema["properties"]["meats"]
    assert schema["minItems"] == 2
    assert "meats" in form.schema["required"]


def test_numeric_bounds_map_to_minimum_and_maximum() -> None:
    form = _build(
        PropertyConstraints(
            path=f"{FOOD}spiceLevel",
            name="spiceLevel",
            datatype=str(XSD.integer),
            min_count=1,
            max_count=1,
            min_inclusive=Decimal(0),
            max_inclusive=Decimal(5),
        )
    )
    schema = form.schema["properties"]["spiceLevel"]
    assert (schema["minimum"], schema["maximum"]) == (0, 5)


def test_decimal_bounds_keep_their_fraction() -> None:
    """`_number` must not truncate a genuinely fractional bound to an int."""
    form = _build(
        PropertyConstraints(
            path=f"{FOOD}weight",
            name="weight",
            datatype=str(XSD.decimal),
            max_count=1,
            min_inclusive=Decimal("0.5"),
        )
    )
    assert form.schema["properties"]["weight"]["minimum"] == 0.5


def test_dates_get_a_json_schema_format() -> None:
    form = _build(
        PropertyConstraints(
            path=f"{FOOD}pickupTime", name="pickupTime", datatype=str(XSD.dateTime), max_count=1
        )
    )
    assert form.schema["properties"]["pickupTime"]["format"] == "date-time"


def test_rdfs_label_wins_over_the_derived_title() -> None:
    form = _build(
        PropertyConstraints(
            path=f"{FOOD}customerNote",
            name="customerNote",
            label="Notes for the kitchen",
            datatype=str(XSD.string),
            max_count=1,
        )
    )
    assert form.schema["properties"]["customerNote"]["title"] == "Notes for the kitchen"


def test_title_is_derived_when_the_shape_gives_no_label() -> None:
    form = _build(
        PropertyConstraints(
            path=f"{FOOD}noodleFirmness",
            name="noodleFirmness",
            datatype=str(XSD.string),
            max_count=1,
        )
    )
    assert form.schema["properties"]["noodleFirmness"]["title"] == "Noodle firmness"


def test_schema_is_closed_to_mirror_sh_closed() -> None:
    form = _build(PropertyConstraints(path=f"{FOOD}size", name="size", max_count=1))
    assert form.schema["additionalProperties"] is False


@pytest.mark.parametrize(
    ("option_count", "expected_format"),
    [(2, "radio"), (3, "radio"), (4, None)],
)
def test_small_enums_render_as_radios(option_count: int, expected_format: str | None) -> None:
    """A rendering hint derived from the constraint count, never from the field's name."""
    options = tuple(_option(f"o{index}", f"Option {index}") for index in range(option_count))
    form = _build(
        PropertyConstraints(
            path=f"{FOOD}size", name="size", node_kind=SH_IRI, max_count=1, options=options
        )
    )
    control = form.uischema["elements"][0]["elements"][0]
    # A control with no hints omits `options` entirely rather than emitting an empty object.
    assert control.get("options", {}).get("format") == expected_format


def test_long_text_renders_multiline() -> None:
    form = _build(
        PropertyConstraints(
            path=f"{FOOD}customerNote",
            name="customerNote",
            datatype=str(XSD.string),
            max_count=1,
            max_length=280,
        )
    )
    control = form.uischema["elements"][0]["elements"][0]
    assert control["options"]["multi"] is True


def test_groups_become_ordered_ui_groups() -> None:
    core = PropertyGroup(iri=f"{FOOD}CoreGroup", label="Your dish", order=Decimal(1))
    extras = PropertyGroup(iri=f"{FOOD}ExtrasGroup", label="Extras", order=Decimal(2))
    form = _build(
        PropertyConstraints(path=f"{FOOD}b", name="b", group=extras, max_count=1),
        PropertyConstraints(path=f"{FOOD}a", name="a", group=core, max_count=1),
    )
    labels = [element["label"] for element in form.uischema["elements"]]
    assert labels == ["Your dish", "Extras"]


def test_ungrouped_properties_are_not_dropped() -> None:
    """A shape that forgets sh:group must still produce a reachable control."""
    core = PropertyGroup(iri=f"{FOOD}CoreGroup", label="Your dish", order=Decimal(1))
    form = _build(
        PropertyConstraints(path=f"{FOOD}a", name="a", group=core, max_count=1),
        PropertyConstraints(path=f"{FOOD}orphan", name="orphan", max_count=1),
    )
    scopes = {
        control["scope"] for group in form.uischema["elements"] for control in group["elements"]
    }
    assert "#/properties/orphan" in scopes


def test_enumerated_terms_get_a_vocab_context_entry() -> None:
    """`@type: @vocab` is what turns the token on the wire into an IRI sh:in can match."""
    form = _build(
        PropertyConstraints(
            path=f"{FOOD}broth",
            name="broth",
            node_kind=SH_IRI,
            max_count=1,
            options=(_option("shio", "Shio"),),
        )
    )
    assert form.context["broth"] == {"@id": f"{FOOD}broth", "@type": "@vocab"}


def test_multi_valued_context_entries_are_sets() -> None:
    form = _build(
        PropertyConstraints(
            path=f"{FOOD}topping",
            name="toppings",
            node_kind=SH_IRI,
            max_count=5,
            options=(_option("nori", "Nori"),),
        )
    )
    assert form.context["toppings"]["@container"] == "@set"


def test_literal_context_entries_carry_their_datatype() -> None:
    form = _build(
        PropertyConstraints(
            path=f"{FOOD}quantity", name="quantity", datatype=str(XSD.integer), max_count=1
        )
    )
    assert form.context["quantity"]["@type"] == str(XSD.integer)


def test_surcharges_are_collected_per_field() -> None:
    form = _build(
        PropertyConstraints(
            path=f"{FOOD}topping",
            name="toppings",
            node_kind=SH_IRI,
            max_count=5,
            options=(_option("chashu", "Chashu", "3.0"), _option("nori", "Nori", "1.0")),
        )
    )
    assert form.surcharges["toppings"] == {"chashu": Decimal("3.0"), "nori": Decimal("1.0")}


def test_base_context_is_preserved() -> None:
    form = build_form(
        (PropertyConstraints(path=f"{FOOD}size", name="size", max_count=1),),
        base_context={"@vocab": FOOD, "name": "https://schema.org/name"},
        title="Test",
    )
    assert form.context["name"] == "https://schema.org/name"
