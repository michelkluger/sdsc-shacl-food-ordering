"""The contract every dish must satisfy, whatever it is.

This module is the executable form of the task's central claim: a dish is added by dropping two
data files on disk, and nothing else has to change. Every test here is parametrised over the
catalogue as discovered at collection time (see ``conftest.pytest_generate_tests``), so the
third dish is held to exactly this contract without a line being added to this file.

If one of these fails for a newly added dish, the dish's shape is wrong - not the code.
"""

from __future__ import annotations

from typing import Any

import pytest
from jsonschema import Draft7Validator
from jsonschema.exceptions import SchemaError

from food_api.catalog.registry import Dish
from food_api.shacl.validate import price_order, validate_order
from tests.conftest import fixture_names, load_fixture


def test_schema_is_a_valid_json_schema(dish: Dish) -> None:
    """The generated schema must itself be legal draft-07, or no client can use it."""
    try:
        Draft7Validator.check_schema(dish.form.schema)
    except SchemaError as exc:  # pragma: no cover - only reached by a broken translator
        pytest.fail(f"{dish.slug}: generated schema is not valid draft-07: {exc}")


def test_required_fields_all_exist(dish: Dish) -> None:
    properties = dish.form.schema["properties"]
    missing = [name for name in dish.form.schema.get("required", []) if name not in properties]
    assert not missing, f"{dish.slug}: required names absent from properties: {missing}"


def test_every_uischema_scope_resolves(dish: Dish) -> None:
    """A control pointing at a property that does not exist renders as a blank gap."""
    properties = dish.form.schema["properties"]
    for scope in _scopes(dish.form.uischema):
        name = scope.removeprefix("#/properties/")
        assert name in properties, f"{dish.slug}: uischema scope {scope} has no schema property"


def test_every_property_has_a_control(dish: Dish) -> None:
    """Every field the shape declares must be reachable in the UI, or it can never be filled."""
    scoped = {scope.removeprefix("#/properties/") for scope in _scopes(dish.form.uischema)}
    missing = set(dish.form.schema["properties"]) - scoped
    assert not missing, f"{dish.slug}: schema properties with no control: {sorted(missing)}"


def test_context_covers_every_property(dish: Dish) -> None:
    """Without a context term a submitted field lifts to nothing and is silently ignored."""
    for name in dish.form.schema["properties"]:
        assert name in dish.form.context, f"{dish.slug}: {name!r} missing from the JSON-LD context"


def test_key_map_is_bijective(dish: Dish) -> None:
    """Error mapping depends on path -> key being one-to-one with the schema's keys."""
    assert set(dish.form.key_by_path.values()) == set(dish.form.schema["properties"])


def test_defaults_satisfy_their_own_schema(dish: Dish) -> None:
    """A shape's sh:defaultValue must be a value the same shape would accept."""
    for name, subschema in dish.form.schema["properties"].items():
        if "default" not in subschema:
            continue
        errors = list(Draft7Validator(subschema).iter_errors(subschema["default"]))
        assert not errors, f"{dish.slug}: default for {name!r} violates its schema: {errors[0]}"


def test_has_at_least_one_valid_fixture(dish: Dish) -> None:
    """A dish with no valid fixture is a dish nobody has proved can be ordered."""
    assert fixture_names(dish.slug, "valid"), (
        f"{dish.slug}: add tests/fixtures/orders/{dish.slug}/valid.json"
    )


def test_valid_fixtures_conform(dish: Dish) -> None:
    for name in fixture_names(dish.slug, "valid"):
        payload = load_fixture(dish.slug, name)["data"]
        outcome = validate_order(dish, payload)
        assert outcome.conforms, (
            f"{dish.slug}/{name} should conform but reported: "
            f"{[violation.message for violation in outcome.violations]}"
        )


def test_valid_fixtures_also_satisfy_the_generated_schema(dish: Dish) -> None:
    """The form we hand the browser must accept what SHACL accepts.

    The converse does not hold - the schema cannot express the sh:sparql rules - but a payload
    SHACL calls valid being rejected by our own generated schema would mean the translator is
    over-constraining, and a user would be blocked from submitting a legal order.
    """
    validator = Draft7Validator(dish.form.schema)
    for name in fixture_names(dish.slug, "valid"):
        payload = load_fixture(dish.slug, name)["data"]
        errors = sorted(validator.iter_errors(payload), key=str)
        assert not errors, f"{dish.slug}/{name} rejected by the generated schema: {errors[0]}"


def test_invalid_fixtures_are_rejected_at_the_declared_pointers(dish: Dish) -> None:
    """Each invalid fixture must fail, and fail where its own description says it will."""
    names = fixture_names(dish.slug, "invalid")
    assert names, f"{dish.slug}: no invalid fixtures - the failure paths are untested"

    for name in names:
        fixture = load_fixture(dish.slug, name)
        outcome = validate_order(dish, fixture["data"])
        assert not outcome.conforms, f"{dish.slug}/{name} was expected to be rejected"

        pointers = {violation.pointer for violation in outcome.violations}
        for expected in fixture.get("expectedPointers", []):
            assert expected in pointers, (
                f"{dish.slug}/{name}: expected a violation at {expected}, got {sorted(pointers)}"
            )

        expected_constraint = fixture.get("expectedConstraint")
        if expected_constraint:
            found = {violation.constraint for violation in outcome.violations}
            assert expected_constraint in found, (
                f"{dish.slug}/{name}: expected {expected_constraint}, got {sorted(found)}"
            )


def test_every_violation_carries_an_actionable_message(dish: Dish) -> None:
    for name in fixture_names(dish.slug, "invalid"):
        outcome = validate_order(dish, load_fixture(dish.slug, name)["data"])
        for violation in outcome.violations:
            assert violation.message.strip(), f"{dish.slug}/{name}: empty violation message"
            assert "urn:food:order:" not in violation.message, (
                f"{dish.slug}/{name}: message leaks the internal order IRI"
            )


#: The shared `food:CustomerNameProperty` says it allows no leading or trailing whitespace. The
#: trailing-newline cases are why this test exists: SHACL specifies XPath regexes, where `$`
#: means end-of-string, but pySHACL compiles `sh:pattern` with Python's `re`, where `$` *also*
#: matches immediately before a single trailing newline. The pattern therefore used to accept
#: "Ada Lovelace\n" - a value its own comment says it rejects. It is anchored with `\Z` now, and
#: these pin that down.
PADDED_NAMES: list[str] = [
    " Ada Lovelace",
    "Ada Lovelace ",
    "Ada Lovelace\n",
    "Ada Lovelace\r\n",
    "\nAda Lovelace",
    "Ada Lovelace\t",
]

#: Internal spaces, hyphens, apostrophes and non-ASCII letters are all ordinary in a name. The
#: shape deliberately constrains shape rather than alphabet, and these are the counterweight to
#: the test above: a pattern that rejected everything would satisfy it.
ORDINARY_NAMES: list[str] = ["Ada Lovelace", "Jean-Luc", "O'Brien", "Ursula Le Guin", "山田"]


def _uses_shared_name(dish: Dish) -> bool:
    return "customerName" in dish.form.schema["properties"]


@pytest.mark.parametrize("name", PADDED_NAMES, ids=repr)
def test_a_padded_customer_name_is_rejected(dish: Dish, name: str) -> None:
    """Whitespace at either end must fail, however the string happens to end.

    Parametrised over dishes because `customerName` comes from `shapes/common.ttl`: every dish
    reusing it inherits the constraint, and a dish that stops reusing it should stop being
    asserted against it rather than quietly passing.
    """
    if not _uses_shared_name(dish):
        pytest.skip(f"{dish.slug} does not use the shared customerName property")

    payload = {**load_fixture(dish.slug, "valid.json")["data"], "customerName": name}
    outcome = validate_order(dish, payload)

    assert not outcome.conforms, f"{dish.slug}: accepted a padded name {name!r}"
    assert any(violation.field == "customerName" for violation in outcome.violations), (
        f"{dish.slug}: {name!r} was rejected, but not at customerName: "
        f"{[violation.field for violation in outcome.violations]}"
    )


@pytest.mark.parametrize("name", ORDINARY_NAMES, ids=repr)
def test_an_ordinary_customer_name_is_accepted(dish: Dish, name: str) -> None:
    """A name someone actually has must go through."""
    if not _uses_shared_name(dish):
        pytest.skip(f"{dish.slug} does not use the shared customerName property")

    payload = {**load_fixture(dish.slug, "valid.json")["data"], "customerName": name}
    outcome = validate_order(dish, payload)

    assert outcome.conforms, (
        f"{dish.slug}: rejected the ordinary name {name!r}: "
        f"{[violation.message for violation in outcome.violations]}"
    )


def test_pricing_is_at_least_the_base_price(dish: Dish) -> None:
    payload = load_fixture(dish.slug, "valid.json")["data"]
    assert price_order(dish, payload) >= dish.summary.base_price


def _scopes(uischema: dict[str, Any]) -> list[str]:
    """Collect every ``scope`` in a UI schema, at any nesting depth."""
    found: list[str] = []
    stack: list[Any] = [uischema]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if isinstance(node.get("scope"), str):
                found.append(node["scope"])
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return found
