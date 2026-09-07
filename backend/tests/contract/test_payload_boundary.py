"""The boundary between a form submission and the JSON-LD document it becomes.

Every other test in this suite asks whether a *well-formed* submission is judged correctly. This
one asks a different question: can a client change the terms on which it is judged at all?

It exists because it could. `build_document` used to spread the payload *after* the server's
keys, so `{"@context": {}}` replaced the generated context, the payload lifted to an empty
graph, `sh:targetClass food:Order` matched nothing, and pySHACL reported `conforms` on a
submission it had never looked at - a 201 with a priced receipt, and not one constraint applied.

That is the worst failure mode a validator has, because it is indistinguishable from working.
`sh:closed` cannot catch it: closure polices predicates, and a JSON-LD keyword never becomes one
- it is consumed while the document is read, and decides how everything else is read.

Parametrised over the catalogue like the rest of the contract suite, so a fourth dish is held to
this the moment its files land.
"""

from __future__ import annotations

from typing import Any

import pytest

from food_api.catalog.registry import Dish
from food_api.jsonld import lift
from food_api.jsonld.lift import LiftError, build_document
from food_api.shacl.validate import validate_order

#: Keywords that decide how a document is read rather than what it says. `@context` and `@type`
#: are the live bypasses; the rest are here because the rule being enforced is "the whole `@`
#: namespace", not a list of the three we happened to think of.
KEYWORDS: list[tuple[str, Any]] = [
    ("@context", {}),
    ("@context", {"@vocab": "https://elsewhere.example/"}),
    ("@type", "food:NotAnOrder"),
    ("@id", "urn:food:order:chosen-by-the-client"),
    ("@graph", [{"@id": "urn:x"}]),
    ("@nest", {}),
    ("@reverse", {}),
]

KEYWORD_IDS = ["context-empty", "context-rewritten", "type", "id", "graph", "nest", "reverse"]


@pytest.mark.parametrize(("keyword", "value"), KEYWORDS, ids=KEYWORD_IDS)
def test_a_json_ld_keyword_in_the_payload_is_refused(dish: Dish, keyword: str, value: Any) -> None:
    """A keyword must be rejected, and rejected *as* a keyword.

    Asserting only `not conforms` would pass for the wrong reason: a payload of nothing but
    `{"@type": ...}` is also missing every required field. The constraint name is what
    distinguishes "refused at the door" from "happened to fail something else later".
    """
    outcome = validate_order(dish, {keyword: value})

    assert not outcome.conforms, f"{dish.slug}: payload keyword {keyword!r} was accepted"
    constraints = {violation.constraint for violation in outcome.violations}
    assert constraints == {"MalformedPayload"}, (
        f"{dish.slug}: {keyword!r} should be refused before lifting, got {sorted(constraints)}"
    )
    assert keyword in outcome.violations[0].message


def test_the_original_bypass_stays_closed(dish: Dish) -> None:
    """The exact payload that used to come back 201 with a 99x priced receipt.

    Kept separate from the sweep above because this one is a regression, not a rule: it is the
    request that actually got through.
    """
    outcome = validate_order(dish, {"@context": {}, "quantity": 99})
    assert not outcome.conforms


def test_a_keyword_is_refused_even_beside_a_valid_submission(
    dish: Dish, valid_payload: Any
) -> None:
    """The check must not depend on the rest of the payload being wrong.

    A keyword smuggled into an otherwise perfect order is the realistic attempt, and the one an
    implementation that only rejects documents it already dislikes would let through.
    """
    payload = dict(valid_payload(dish.slug))
    assert validate_order(dish, payload).conforms, "the fixture should be valid to begin with"

    outcome = validate_order(dish, {**payload, "@context": {}})
    assert not outcome.conforms
    assert {violation.constraint for violation in outcome.violations} == {"MalformedPayload"}


def test_the_server_still_owns_the_document_if_the_keyword_check_is_removed(
    dish: Dish,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The second line of defence, tested with the first one disabled.

    `build_document` spreads the server's keys *after* the payload, so they win. That defence is
    real but invisible - it is nothing but the position of `**payload` in a dict literal, and a
    refactor that reads as tidying can reverse it. Neutralising the keyword check is the only way
    to assert the ordering actually holds rather than assuming the check hides the question.
    """
    monkeypatch.setattr(lift, "_reject_keywords", lambda payload: None)

    document = build_document(
        dish,
        {
            "@context": {"quantity": "https://elsewhere.example/anything"},
            "@id": "urn:food:order:chosen-by-the-client",
            "@type": "food:NotAnOrder",
            "dish": "some-other-dish",
        },
        "urn:food:order:server-minted",
    )

    assert document["@context"] == dish.form.context
    assert document["@id"] == "urn:food:order:server-minted"
    assert document["@type"] == "food:Order"
    assert document["dish"] == dish.slug


def test_a_dish_key_cannot_redirect_the_order(dish: Dish, valid_payload: Any) -> None:
    """`food:dish` is in `sh:ignoredProperties`, so closure will not catch a client-set one.

    It is also not a keyword, so it reaches `build_document` for real - which makes the ordering
    there the only thing between a submission and a receipt for a different dish.
    """
    payload = dict(valid_payload(dish.slug))
    document = build_document(dish, {**payload, "dish": "some-other-dish"}, "urn:x")
    assert document["dish"] == dish.slug


def test_a_plain_payload_still_lifts_unchanged(dish: Dish, valid_payload: Any) -> None:
    """The guard must not have made ordinary submissions harder.

    Cheap to assert, and the first thing a heavy-handed fix breaks.
    """
    payload = dict(valid_payload(dish.slug))
    document = build_document(dish, payload, "urn:x")
    for key, value in payload.items():
        assert document[key] == value


def test_the_refusal_names_every_keyword_it_found(dish: Dish) -> None:
    """A client sending two keywords should be told about both, not just the first."""
    with pytest.raises(LiftError) as caught:
        build_document(dish, {"@context": {}, "@type": "food:X"}, "urn:x")

    assert "'@context'" in str(caught.value)
    assert "'@type'" in str(caught.value)
