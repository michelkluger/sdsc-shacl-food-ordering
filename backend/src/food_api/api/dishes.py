"""Dish listing and form retrieval.

There is no per-dish route and no dish-specific branch anywhere in this module. ``/{slug}/form``
serves whatever the shape for that slug says, in whatever language was negotiated, which is what
allows a new dish - or a new language - to appear in the API the moment its data files land on
disk.
"""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from food_api.api.deps import CatalogDep, DishDep
from food_api.api.language import LanguageDep
from food_api.domain.models import DishSummaryModel, FormResponse, PricingHint
from food_api.shacl.introspect import SUPPORTED_LANGUAGES

router = APIRouter(prefix="/dishes", tags=["dishes"])


@router.get(
    "",
    summary="List every dish on the menu",
    response_model=list[DishSummaryModel],
)
async def list_dishes(
    catalog: CatalogDep,
    language: LanguageDep,
    response: Response,
) -> list[DishSummaryModel]:
    response.headers["Content-Language"] = language
    return [
        DishSummaryModel.model_validate(dish.summary_for(language).as_dict())
        for dish in catalog.list_dishes()
    ]


@router.get(
    "/{slug}",
    summary="Retrieve one dish's catalogue entry",
    response_model=DishSummaryModel,
    responses={status.HTTP_404_NOT_FOUND: {"description": "No such dish"}},
)
async def get_dish_summary(
    dish: DishDep,
    language: LanguageDep,
    response: Response,
) -> DishSummaryModel:
    response.headers["Content-Language"] = language
    return DishSummaryModel.model_validate(dish.summary_for(language).as_dict())


@router.get(
    "/{slug}/form",
    summary="Retrieve the JSON Forms schema pair generated from the dish's SHACL shape",
    response_model=FormResponse,
    response_model_by_alias=True,
    responses={status.HTTP_404_NOT_FOUND: {"description": "No such dish"}},
)
async def get_dish_form(dish: DishDep, language: LanguageDep, response: Response) -> FormResponse:
    """Return the schema, UI schema and JSON-LD context for a dish.

    All of them are generated at startup, once per language, and then served from memory: the
    translation is pure, so there is nothing to recompute per request.

    Only the human-readable strings differ between languages. The JSON keys, the context terms
    and the constraints are identical, so a form fetched in Romansh submits to the same endpoint
    and is validated by the same shape as one fetched in English.
    """
    form = dish.form_for(language)
    summary = dish.summary_for(language)
    response.headers["Content-Language"] = form.language

    # Constructed by field name rather than by alias: `populate_by_name` accepts both, and
    # `@context` is not a legal Python identifier so passing it by alias needs kwargs unpacking
    # that no type checker can see through. Serialisation still emits the aliases.
    return FormResponse(
        dish=DishSummaryModel.model_validate(summary.as_dict()),
        json_schema=form.schema,
        uischema=form.uischema,
        context=form.context,
        shape_iri=str(dish.node_shape),
        language=form.language,
        available_languages=list(SUPPORTED_LANGUAGES),
        pricing=PricingHint(
            basePrice=float(summary.base_price),
            currency=summary.currency,
            surcharges={
                field: {token: float(amount) for token, amount in options.items()}
                for field, options in form.surcharges.items()
            },
            multiplierField=form.multiplier_field,
        ),
    )
