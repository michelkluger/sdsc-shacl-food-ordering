"""Request dependencies.

The catalogue and the search port are built once during the lifespan and stored on
``app.state``. Reaching them through dependencies rather than module globals is what lets a
test swap in :class:`~food_api.search.client.InMemorySearch` or a catalogue pointed at a
fixture directory without patching imports.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Path, Query, Request

from food_api.catalog.registry import Catalog, Dish
from food_api.core.errors import DishNotFoundError
from food_api.core.language import negotiate
from food_api.search.client import SearchPort


def get_catalog(request: Request) -> Catalog:
    return request.app.state.catalog


def get_search(request: Request) -> SearchPort:
    return request.app.state.search


CatalogDep = Annotated[Catalog, Depends(get_catalog)]
SearchDep = Annotated[SearchPort, Depends(get_search)]


def get_dish(
    catalog: CatalogDep,
    slug: Annotated[str, Path(description="The dish's directory name, e.g. `ramen`.")],
) -> Dish:
    """Resolve a path slug to a dish, or raise a 404 problem detail listing what does exist."""
    dish = catalog.get(slug)
    if dish is None:
        raise DishNotFoundError(slug, catalog.slugs)
    return dish


DishDep = Annotated[Dish, Depends(get_dish)]


def get_language(
    request: Request,
    lang: Annotated[
        str | None,
        Query(description="Force a language: `en`, `de`, `fr`, `it` or `rm`.", max_length=16),
    ] = None,
) -> str:
    """Resolve the language for this request. See ``core/language.py`` for the rules."""
    return negotiate(request.headers.get("accept-language"), lang)


LanguageDep = Annotated[str, Depends(get_language)]
