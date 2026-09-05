"""Validate a submitted order against its dish's SHACL shape.

This is the authority on whether an order is acceptable. The JSON Schema handed to the browser
is a rendering hint that helps a user get it right first time; it is not consulted here, and a
payload that satisfies it can still be rejected by a ``sh:sparql`` cross-field rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import pyshacl

from food_api.catalog.registry import Dish
from food_api.jsonld.lift import LiftError, new_order_iri, to_graph
from food_api.shacl.report import Violation, collect_violations


@dataclass(frozen=True, slots=True)
class ValidationOutcome:
    """The result of validating one order."""

    conforms: bool
    violations: tuple[Violation, ...]
    order_iri: str
    #: pySHACL's human-readable report. Returned only in debug mode; useful when a shape,
    #: rather than a payload, is the thing that is wrong.
    report_text: str = ""


def validate_order(dish: Dish, payload: dict[str, Any]) -> ValidationOutcome:
    """Validate ``payload`` against ``dish``'s shape and return structured violations.

    ``advanced=True`` is required: without it pySHACL skips ``sh:sparql`` entirely and every
    cross-field rule silently passes. ``inference="none"`` keeps the data graph exactly as
    submitted, so a violation always points at something the client actually sent.
    """
    order_iri = new_order_iri()
    try:
        data_graph = to_graph(dish, payload, order_iri)
    except LiftError as exc:
        return ValidationOutcome(
            conforms=False,
            violations=(
                Violation(
                    pointer="",
                    field=None,
                    path=None,
                    constraint="MalformedPayload",
                    severity="violation",
                    message=str(exc),
                ),
            ),
            order_iri=order_iri,
        )

    conforms, report_graph, report_text = pyshacl.validate(
        data_graph,
        shacl_graph=dish.shapes_graph,
        advanced=True,
        inference="none",
        allow_warnings=False,
    )

    violations = () if conforms else tuple(collect_violations(report_graph, dish.form, payload))
    return ValidationOutcome(
        conforms=bool(conforms),
        violations=violations,
        order_iri=order_iri,
        report_text=report_text,
    )


def price_order(dish: Dish, payload: dict[str, Any]) -> Decimal:
    """Price a validated order from the surcharges annotated on the chosen option terms.

    Pricing reads ``food:surcharge`` from the vocabulary via the form's surcharge map, so a new
    option's price is set where the option is defined - not in a lookup table in Python that
    someone has to remember to update.
    """
    total = dish.summary.base_price
    for field_name, per_token in dish.form.surcharges.items():
        chosen = payload.get(field_name)
        tokens = chosen if isinstance(chosen, list) else [chosen] if chosen is not None else []
        for token in tokens:
            total += per_token.get(str(token), Decimal(0))

    quantity = payload.get("quantity", 1)
    if isinstance(quantity, int) and quantity > 0:
        total *= quantity
    return total.quantize(Decimal("0.01"))
