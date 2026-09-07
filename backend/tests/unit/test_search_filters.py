"""Filter-expression building.

Meilisearch filters are an expression language and the SDK has no placeholder binding, so every
query parameter that reaches a filter is string-interpolated into one. That makes the quoting in
`_quote` the entire boundary between a search parameter and executable filter syntax, which is
worth pinning down here rather than only in the integration suite: these run without a container,
so a regression fails in seconds instead of behind a Docker service.

`tests/api` asserts the same thing end-to-end over HTTP, and `tests/integration` asserts that
real Meilisearch agrees with the escaping this module produces.
"""

from __future__ import annotations

import pytest

from food_api.api.routes.search import SearchQuery, _quote


def test_an_ordinary_value_is_simply_quoted() -> None:
    assert _quote("Japanese") == "'Japanese'"


def test_a_single_quote_is_escaped_not_closed() -> None:
    """The whole point: an embedded quote must stay inside the literal."""
    assert _quote("rock 'n roll") == r"'rock \'n roll'"


def test_a_backslash_is_escaped_before_the_quote_is() -> None:
    """Order matters.

    Escaping the quote first and the backslash second would double the backslash that was just
    added, turning `\\'` into `\\\\'` - an escaped backslash followed by a *live* quote, which
    closes the literal. This is the classic way a hand-rolled escaper stays exploitable.
    """
    assert _quote("back\\slash") == r"'back\\slash'"
    assert _quote("\\'") == r"'\\\''"


def test_an_empty_value_is_still_a_literal() -> None:
    assert _quote("") == "''"


@pytest.mark.parametrize(
    "injection",
    [
        "Japanese' OR cuisine = 'French",
        "x' OR slug EXISTS OR slug = '",
        "' OR NOT slug = 'nothing",
    ],
)
def test_an_injection_attempt_stays_one_literal(injection: str) -> None:
    """A filter must come out as exactly one `attribute = 'value'` clause.

    Asserting on the string rather than on a search result because this is the property that
    matters: whatever the client sends, it lands inside the quotes. Counting unescaped quotes is
    how you check that - there should be exactly the two that delimit the literal.
    """
    (expression,) = SearchQuery(cuisine=injection).filters()

    assert expression.startswith("cuisine = '")
    assert expression.endswith("'")
    assert _unescaped_quotes(expression) == 2


def test_every_filter_parameter_goes_through_the_same_quoting() -> None:
    """A filter added later must not be able to forget.

    `cuisine`, `diet` and each `allergenFree` all interpolate a client-supplied value, so all
    four expressions are checked - a fix applied only to the parameter that was reported is not
    a fix. `OR` appearing *inside* a literal is harmless and expected; an unescaped quote, which
    would let it out, is not.
    """
    hostile = "x' OR slug EXISTS OR slug = '"
    expressions = SearchQuery(
        cuisine=hostile,
        diet=hostile,
        allergen_free=[hostile, hostile],
    ).filters()

    assert len(expressions) == 4
    for expression in expressions:
        _, _, literal = expression.partition(" ")[2].partition(" ")
        assert _unescaped_quotes(literal) == 2, expression


def _unescaped_quotes(expression: str) -> int:
    """Count the quotes that Meilisearch would read as literal delimiters.

    Exactly two means the value is wholly contained: one to open, one to close. More means the
    client managed to close the literal early and append syntax of its own.
    """
    return expression.replace(r"\\", "").replace(r"\'", "").count("'")


def test_absent_parameters_contribute_no_filter() -> None:
    """An empty filter list means "no filter", not "filter on empty string"."""
    assert SearchQuery().filters() == []
    assert SearchQuery(cuisine="", diet=None, allergen_free=[]).filters() == []
