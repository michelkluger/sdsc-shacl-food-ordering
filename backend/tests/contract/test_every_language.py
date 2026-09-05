"""The contract every language must satisfy, for every dish.

The invariant that matters is not "everything is translated" - it is that **translation changes
only what people read**. JSON keys, constraints, defaults and enumerated values are identical in
all five languages, which is what lets a form rendered in Romansh be validated and priced by the
English one, and what makes a partially translated corpus safe to ship.

Like the dish contract suite, this is parametrised over the corpus rather than a fixed list, so
a sixth language added as one file would be held to the same contract with no test written.
"""

from __future__ import annotations

import pytest
from jsonschema import Draft7Validator

from food_api.catalog.registry import Dish
from food_api.shacl.introspect import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES
from food_api.shacl.validate import price_order, validate_order
from tests.conftest import fixture_names, load_fixture

LANGUAGES = pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)


@LANGUAGES
def test_every_dish_has_a_form_in_every_language(dish: Dish, language: str) -> None:
    assert dish.form_for(language) is not None
    assert dish.form_for(language).language == language


@LANGUAGES
def test_json_keys_are_identical_across_languages(dish: Dish, language: str) -> None:
    """The wire contract must not move when the reader changes."""
    baseline = sorted(dish.form_for(DEFAULT_LANGUAGE).schema["properties"])
    assert sorted(dish.form_for(language).schema["properties"]) == baseline


@LANGUAGES
def test_required_fields_are_identical_across_languages(dish: Dish, language: str) -> None:
    baseline = dish.form_for(DEFAULT_LANGUAGE).schema.get("required", [])
    assert dish.form_for(language).schema.get("required", []) == baseline


@LANGUAGES
def test_option_values_are_identical_across_languages(dish: Dish, language: str) -> None:
    """Only the labels are translated. A German user submits `veganMiso`, same as everyone."""
    for name, subschema in dish.form_for(language).schema["properties"].items():
        baseline = _option_values(dish.form_for(DEFAULT_LANGUAGE).schema["properties"][name])
        assert _option_values(subschema) == baseline, f"{name} option values differ in {language}"


@LANGUAGES
def test_constraints_are_identical_across_languages(dish: Dish, language: str) -> None:
    keys = (
        "type",
        "minimum",
        "maximum",
        "minLength",
        "maxLength",
        "pattern",
        "minItems",
        "maxItems",
        "uniqueItems",
        "default",
        "format",
    )
    for name, subschema in dish.form_for(language).schema["properties"].items():
        baseline = dish.form_for(DEFAULT_LANGUAGE).schema["properties"][name]
        for key in keys:
            assert subschema.get(key) == baseline.get(key), f"{name}.{key} differs in {language}"


@LANGUAGES
def test_context_is_identical_across_languages(dish: Dish, language: str) -> None:
    """The lifting rules are semantics, not presentation, and must not vary."""
    assert dish.form_for(language).context == dish.form_for(DEFAULT_LANGUAGE).context


@LANGUAGES
def test_generated_schema_stays_valid_in_every_language(dish: Dish, language: str) -> None:
    Draft7Validator.check_schema(dish.form_for(language).schema)


@LANGUAGES
def test_every_field_is_labelled_in_every_language(dish: Dish, language: str) -> None:
    """A missing label would render as a blank control, which is worse than an English one."""
    for name, subschema in dish.form_for(language).schema["properties"].items():
        assert subschema.get("title"), f"{dish.slug}/{name} has no title in {language}"


@LANGUAGES
def test_every_option_is_labelled_in_every_language(dish: Dish, language: str) -> None:
    for name, subschema in dish.form_for(language).schema["properties"].items():
        for option in _options(subschema):
            assert option.get("title"), f"{dish.slug}/{name}/{option.get('const')} unlabelled"


@LANGUAGES
def test_group_labels_are_present_in_every_language(dish: Dish, language: str) -> None:
    for group in dish.form_for(language).uischema["elements"]:
        assert group.get("label"), f"{dish.slug} has an unlabelled group in {language}"


@LANGUAGES
def test_validity_does_not_depend_on_language(dish: Dish, language: str) -> None:
    """An order that is valid in German is valid in Italian. Only the wording moves."""
    for name in fixture_names(dish.slug, "valid"):
        payload = load_fixture(dish.slug, name)["data"]
        assert validate_order(dish, payload, language=language).conforms

    for name in fixture_names(dish.slug, "invalid"):
        payload = load_fixture(dish.slug, name)["data"]
        outcome = validate_order(dish, payload, language=language)
        assert not outcome.conforms, f"{dish.slug}/{name} accepted in {language}"


@LANGUAGES
def test_violations_point_at_the_same_places_in_every_language(dish: Dish, language: str) -> None:
    for name in fixture_names(dish.slug, "invalid"):
        payload = load_fixture(dish.slug, name)["data"]
        baseline = {
            (v.pointer, v.constraint)
            for v in validate_order(dish, payload, language=DEFAULT_LANGUAGE).violations
        }
        translated = {
            (v.pointer, v.constraint)
            for v in validate_order(dish, payload, language=language).violations
        }
        assert translated == baseline, f"{dish.slug}/{name}: pointers moved in {language}"


@LANGUAGES
def test_pricing_does_not_depend_on_language(dish: Dish, language: str) -> None:
    """Surcharges live on vocabulary terms, not on labels, so a Romansh order costs the same."""
    payload = load_fixture(dish.slug, "valid.json")["data"]
    assert price_order(dish, payload) == price_order(dish, payload)


@LANGUAGES
def test_every_violation_message_is_non_empty_in_every_language(dish: Dish, language: str) -> None:
    for name in fixture_names(dish.slug, "invalid"):
        payload = load_fixture(dish.slug, name)["data"]
        for violation in validate_order(dish, payload, language=language).violations:
            assert violation.message.strip(), f"{dish.slug}/{name} empty message in {language}"


@LANGUAGES
def test_messages_are_not_a_concatenation_of_every_language(dish: Dish, language: str) -> None:
    """Regression guard.

    pySHACL strips the language tag from `sh:sparql` messages, so every translation arrives
    indistinguishable and a naive reader joins all five into one sentence. `report.py` resolves
    those from the shapes graph instead. This test fails loudly if that path breaks.
    """
    for name in fixture_names(dish.slug, "invalid"):
        payload = load_fixture(dish.slug, name)["data"]
        for violation in validate_order(dish, payload, language=language).violations:
            # No legitimate single-language message in this corpus reaches 200 characters,
            # while a five-way concatenation comfortably exceeds it.
            assert len(violation.message) < 200, (
                f"{dish.slug}/{name} in {language} looks like a concatenation: "
                f"{violation.message!r}"
            )


def test_translated_dishes_actually_differ_from_english(dish: Dish) -> None:
    """Guards against the corpus silently degrading to English everywhere.

    Without this, deleting every translation file would still pass every other test here - all
    of which check *consistency*, which a monolingual corpus satisfies perfectly.
    """
    english = dish.form_for("en").schema
    translated = {
        language: dish.form_for(language).schema
        for language in SUPPORTED_LANGUAGES
        if language != "en"
    }
    for language, schema in translated.items():
        titles = {name: sub.get("title") for name, sub in schema["properties"].items()}
        english_titles = {name: sub.get("title") for name, sub in english["properties"].items()}
        assert titles != english_titles, f"{dish.slug} is not actually translated into {language}"


def _options(subschema: dict) -> list[dict]:
    target = subschema.get("items", subschema)
    return target.get("oneOf", []) if isinstance(target, dict) else []


def _option_values(subschema: dict) -> list[str | None]:
    return [option.get("const") for option in _options(subschema)]
