"""Order submission.

The whole endpoint is: lift the payload into RDF using the dish's generated context, hand it to
pySHACL, and translate the report. There is no per-dish validation code, and no Python
re-implementation of any rule that the shape already states.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from food_api.api.deps import DishDep
from food_api.domain.errors import ShaclValidationError
from food_api.domain.models import OrderReceipt, OrderRequest
from food_api.shacl.validate import price_order, validate_order

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post(
    "/{slug}",
    summary="Validate and accept an order for a dish",
    status_code=status.HTTP_201_CREATED,
    response_model=OrderReceipt,
    response_model_by_alias=True,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "No such dish"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "SHACL constraint violations, addressed by JSON pointer",
        },
    },
)
async def submit_order(dish: DishDep, request: OrderRequest) -> OrderReceipt:
    """Validate a submitted form against the dish's SHACL shape.

    Nothing is persisted: the task calls for none, and a receipt that is computed rather than
    stored keeps the demo honest about what it does. The order id is minted per request so a
    client can correlate a receipt with its submission.
    """
    outcome = validate_order(dish, request.data)
    if not outcome.conforms:
        raise ShaclValidationError(dish.slug, outcome.violations)

    return OrderReceipt(
        orderId=outcome.order_iri,
        dish=dish.slug,
        total=float(price_order(dish, request.data)),
        currency=dish.summary.currency,
        data=request.data,
    )
