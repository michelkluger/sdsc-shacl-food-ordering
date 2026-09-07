"""Dish search, backed by Meilisearch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from food_api.api.deps import SearchDep
from food_api.core.errors import SearchDegradedError
from food_api.models import SearchPublic
from food_api.search.client import SearchUnavailableError

router = APIRouter(prefix="/search", tags=["search"])

MAX_LIMIT = 50


def _quote(value: str) -> str:
    """Render ``value`` as a single-quoted Meilisearch filter literal.

    Meilisearch filters are an expression language, not a parameterised query: the SDK offers no
    placeholder binding, so the only defence is to make the quoting correct here. A cuisine of
    ``Japanese' OR slug = 'ramen`` would otherwise close the literal and append a clause of the
    client's choosing.

    Meilisearch's own escape is a backslash before the quote or backslash, so both are escaped
    and the result is wrapped. Doing it in one function rather than at each call site means a
    filter added later cannot forget.
    """
    escaped = value.replace("\\", r"\\").replace("'", r"\'")
    return f"'{escaped}'"


@dataclass
class SearchQuery:
    """The query string parameters, grouped so the handler stays a two-liner.

    FastAPI builds this from the request the same way it would build loose parameters, and it
    keeps the filter-building logic next to the fields it reads.
    """

    q: Annotated[str, Query(description="Free-text query. Empty returns everything.")] = ""
    cuisine: Annotated[str | None, Query(description="Exact cuisine match.")] = None
    diet: Annotated[str | None, Query(description="Dishes offering this diet.")] = None
    allergen_free: Annotated[
        list[str] | None,
        Query(alias="allergenFree", description="Exclude dishes involving these allergens."),
    ] = None
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 20

    def filters(self) -> list[str]:
        """Build Meilisearch filter expressions from the parameters.

        ``allergenFree`` is a negative filter, which is the one a person actually wants: you
        search for food you *can* eat, not for food that contains the thing you react to.
        """
        expressions: list[str] = []
        if self.cuisine:
            expressions.append(f"cuisine = {_quote(self.cuisine)}")
        if self.diet:
            expressions.append(f"diets = {_quote(self.diet)}")
        expressions.extend(
            f"allergens != {_quote(allergen)}" for allergen in self.allergen_free or []
        )
        return expressions


SearchQueryDep = Annotated[SearchQuery, Depends()]


@router.get(
    "",
    summary="Search dishes by text, cuisine, diet and allergens",
    response_model=SearchPublic,
    response_model_by_alias=True,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Meilisearch is unreachable. Forms and ordering are unaffected.",
        },
    },
)
async def search_dishes(search: SearchDep, query: SearchQueryDep) -> SearchPublic:
    try:
        results = await search.search(query.q, filters=query.filters(), limit=query.limit)
    except SearchUnavailableError as exc:
        raise SearchDegradedError(
            "Dish search is temporarily unavailable. Browsing dishes, retrieving forms and "
            f"submitting orders are unaffected. ({exc})"
        ) from exc

    return SearchPublic(
        query=results.query,
        hits=results.hits,
        estimatedTotal=results.estimated_total,
        facets=results.facets,
    )
