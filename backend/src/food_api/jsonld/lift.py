"""Lift a submitted form payload into an RDF graph.

The payload the browser sends is plain JSON. Wrapping it in the dish's generated ``@context``
turns it into JSON-LD, and rdflib turns that into the graph SHACL validates. No field names are
hard-coded here: the context came from the shape, so this module works unchanged for any dish.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from rdflib import Graph

from food_api.catalog.registry import Dish
from food_api.namespaces import ORDER_BASE


class LiftError(ValueError):
    """The payload could not be expressed as JSON-LD."""


def new_order_iri() -> str:
    """Mint a fresh IRI for one order. Orders are not persisted; this only needs to be unique."""
    return f"{ORDER_BASE}{uuid.uuid4()}"


def _reject_keywords(payload: dict[str, Any]) -> None:
    """Raise if the payload carries a JSON-LD keyword.

    Keywords are the document's control plane: ``@context`` decides how every other key is read,
    ``@type`` decides which shapes target the node, ``@graph`` moves the node out of the default
    graph. A client that sets one is not filling in a form, it is rewriting the rules the form
    is checked against - an empty ``@context`` lifts to an empty graph, which SHACL finds
    nothing wrong with.

    Spreading the server's keys last (below) already stops the four keywords this function knows
    are dangerous. This check exists because that defence is invisible - it lives in the order of
    a dict literal, where a refactor can undo it silently - and because it says nothing about the
    keywords JSON-LD may grow next. Refusing the whole ``@`` namespace is a rule that can be
    read, and it turns a bypass attempt into a violation the client is told about.
    """
    keywords = sorted(key for key in payload if key.startswith("@"))
    if keywords:
        listed = ", ".join(repr(keyword) for keyword in keywords)
        raise LiftError(
            f"A form submission may not contain JSON-LD keywords ({listed}); "
            "they are set by the server."
        )


def build_document(dish: Dish, payload: dict[str, Any], order_iri: str) -> dict[str, Any]:
    """Wrap ``payload`` as a JSON-LD document for ``dish``.

    ``dish`` and ``@type`` are set here, by the server, and are listed in the shape's
    ``sh:ignoredProperties``. A client cannot smuggle in a different dish by putting one in the
    body: the server's keys are spread *after* the payload, so they win, and the payload cannot
    carry a keyword at all - :func:`_reject_keywords` has refused it before we get here.

    Both halves matter. Without the ordering, a payload key silently overwrites the server's;
    without the keyword check, a keyword this function does not happen to set would still be
    honoured.
    """
    _reject_keywords(payload)
    return {
        **payload,
        "@context": dish.form.context,
        "@id": order_iri,
        "@type": "food:Order",
        "dish": dish.slug,
    }


def to_graph(dish: Dish, payload: dict[str, Any], order_iri: str) -> Graph:
    """Return the data graph for one submitted order, with the vocabulary merged in.

    The vocabulary has to be part of the *data* graph rather than pyshacl's ``ont_graph``:
    ``sh:sparql`` constraints are evaluated against the data graph only, and our cross-field
    rules query vocabulary annotations such as ``food:excludedByDiet``. Passing it as
    ``ont_graph`` silently produces a graph where those rules never match, which reads as
    "everything is valid" - the most dangerous possible failure for a validator.
    """
    document = build_document(dish, payload, order_iri)
    graph = Graph()
    try:
        graph.parse(data=json.dumps(document), format="json-ld")
    except Exception as exc:
        raise LiftError(f"Payload could not be read as JSON-LD: {exc}") from exc
    graph += dish.vocabulary
    return graph
