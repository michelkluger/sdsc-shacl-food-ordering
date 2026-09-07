"""The IRI helpers.

`localname` is small, but it is shared: the shape reader uses it to derive option tokens and
fallback field names, and the report reader uses it to name a constraint and to recover the
field a `sh:closed` violation is about. It used to exist twice, once in each, which is how "how
we shorten an IRI" quietly becomes two answers. Now that there is one, it is worth pinning down
the edges - especially the ones neither caller exercises today.
"""

from __future__ import annotations

import pytest

from food_api.namespaces import FOOD, localname


@pytest.mark.parametrize(
    ("iri", "expected"),
    [
        ("https://sdsc.example/ns/food#veganMiso", "veganMiso"),
        ("http://www.w3.org/ns/shacl#MinCountConstraintComponent", "MinCountConstraintComponent"),
        # A slash namespace shortens the same way a hash one does.
        ("https://schema.org/name", "name"),
        # Hash wins when both separators appear, which is what every vocabulary here relies on.
        ("https://sdsc.example/ns/food#topping", "topping"),
    ],
)
def test_the_last_segment_is_returned(iri: str, expected: str) -> None:
    assert localname(iri) == expected


def test_a_trailing_separator_falls_through_to_the_next_one() -> None:
    """A namespace IRI has nothing after its ``#``, so the ``/`` before it is used instead.

    Degenerate input - no property path or option term is ever the bare namespace - but worth
    stating, because "returns the last path segment plus a stray hash" is surprising enough to
    be read as a bug by whoever meets it next.
    """
    assert localname("https://sdsc.example/ns/food#") == "food#"


@pytest.mark.parametrize(
    "iri",
    [
        # Every separator is trailing, so there is no tail to take.
        "https://sdsc.example/ns/food/",
        "#",
        # No separator at all, which is what a bare token or a malformed IRI looks like.
        "veganMiso",
        "",
    ],
)
def test_an_iri_with_no_usable_tail_is_returned_whole(iri: str) -> None:
    """Never an empty string: a nameless option or constraint is unreadable in a form."""
    assert localname(iri) == iri


def test_it_agrees_with_the_namespace_it_shortens() -> None:
    """The round trip the whole option-token scheme rests on.

    `FOOD.chashu` is how a term is built; `localname` is how it becomes the token a client sends
    back. If these two ever disagreed, a submitted token would stop matching its own `sh:in`.
    """
    assert localname(str(FOOD.chashu)) == "chashu"
