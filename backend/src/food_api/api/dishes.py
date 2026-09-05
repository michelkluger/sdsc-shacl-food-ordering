"""Dish listing and form retrieval.

There is no per-dish route and no dish-specific branch anywhere in this module. ``/{slug}/form``
serves whatever the shape for that slug says, which is what allows a new dish to appear in the
API the moment its two data files land on disk.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from food_api.api.deps import CatalogDep, DishDep
from food_api.domain.models import DishSummaryModel, FormResponse

router = APIRouter(prefix="/dishes", tags=["dishes"])


@router.get(
    "",
    summary="List every dish on the menu",
    response_model=list[DishSummaryModel],
)
async def list_dishes(catalog: CatalogDep) -> list[DishSummaryModel]:
    return [
        DishSummaryModel.model_validate(dish.summary.as_dict()) for dish in catalog.list_dishes()
    ]


@router.get(
    "/{slug}",
    summary="Retrieve one dish's catalogue entry",
    response_model=DishSummaryModel,
    responses={status.HTTP_404_NOT_FOUND: {"description": "No such dish"}},
)
async def get_dish_summary(dish: DishDep) -> DishSummaryModel:
    return DishSummaryModel.model_validate(dish.summary.as_dict())


@router.get(
    "/{slug}/form",
    summary="Retrieve the JSON Forms schema pair generated from the dish's SHACL shape",
    response_model=FormResponse,
    response_model_by_alias=True,
    responses={status.HTTP_404_NOT_FOUND: {"description": "No such dish"}},
)
async def get_dish_form(dish: DishDep) -> FormResponse:
    """Return the schema, UI schema and JSON-LD context for a dish.

    All three are generated at startup from the shape and then served from memory: the
    translation is pure, so there is nothing to recompute per request.
    """
    # Constructed by field name rather than by alias: `populate_by_name` accepts both, and
    # `@context` is not a legal Python identifier so passing it by alias needs kwargs unpacking
    # that no type checker can see through. Serialisation still emits the aliases.
    return FormResponse(
        dish=DishSummaryModel.model_validate(dish.summary.as_dict()),
        json_schema=dish.form.schema,
        uischema=dish.form.uischema,
        context=dish.form.context,
        shape_iri=str(dish.node_shape),
    )
