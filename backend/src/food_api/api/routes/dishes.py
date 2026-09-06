"""Dish listing and form retrieval.

There is no per-dish route and no dish-specific branch anywhere in this module. ``/{slug}/form``
serves whatever the shape for that slug says, in whatever language was negotiated, which is what
allows a new dish - or a new language - to appear in the API the moment its data files land on
disk.
"""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from food_api.api.deps import CatalogDep, DishDep, LanguageDep
from food_api.models import DishesPublic, DishFormPublic, DishPublic, PricingPublic
from food_api.shacl.introspect import SUPPORTED_LANGUAGES

router = APIRouter(prefix="/dishes", tags=["dishes"])


@router.get(
    "",
    summary="List every dish on the menu",
    response_model=DishesPublic,
)
async def read_dishes(
    catalog: CatalogDep,
    language: LanguageDep,
    response: Response,
) -> DishesPublic:
    response.headers["Content-Language"] = language
    dishes = [
        DishPublic.model_validate(dish.summary_for(language).as_dict())
        for dish in catalog.list_dishes()
    ]
    return DishesPublic(data=dishes, count=len(dishes))


@router.get(
    "/{slug}",
    summary="Retrieve one dish's catalogue entry",
    response_model=DishPublic,
    responses={status.HTTP_404_NOT_FOUND: {"description": "No such dish"}},
)
async def read_dish(
    dish: DishDep,
    language: LanguageDep,
    response: Response,
) -> DishPublic:
    response.headers["Content-Language"] = language
    return DishPublic.model_validate(dish.summary_for(language).as_dict())


@router.get(
    "/{slug}/form",
    summary="Retrieve the JSON Forms schema pair generated from the dish's SHACL shape",
    response_model=DishFormPublic,
    response_model_by_alias=True,
    responses={status.HTTP_404_NOT_FOUND: {"description": "No such dish"}},
)
async def read_dish_form(
    dish: DishDep,
    language: LanguageDep,
    response: Response,
) -> DishFormPublic:
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
    return DishFormPublic(
        dish=DishPublic.model_validate(summary.as_dict()),
        json_schema=form.schema,
        uischema=form.uischema,
        context=form.context,
        shape_iri=str(dish.node_shape),
        language=form.language,
        available_languages=list(SUPPORTED_LANGUAGES),
        pricing=PricingPublic(
            basePrice=float(summary.base_price),
            currency=summary.currency,
            surcharges={
                field: {token: float(amount) for token, amount in options.items()}
                for field, options in form.surcharges.items()
            },
            multiplierField=form.multiplier_field,
        ),
    )
