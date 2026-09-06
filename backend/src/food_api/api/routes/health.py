"""Liveness and readiness.

``/healthz`` reports per-component status rather than a single boolean, because this service
has two very different kinds of dependency: the dish corpus, without which it cannot do its
job at all, and Meilisearch, without which it merely loses one endpoint.
"""

from __future__ import annotations

from fastapi import APIRouter

from food_api import __version__
from food_api.api.deps import CatalogDep, SearchDep
from food_api.models import ComponentPublic, HealthPublic

router = APIRouter(tags=["health"])


@router.get("/healthz", summary="Service and component health", response_model=HealthPublic)
async def read_health(catalog: CatalogDep, search: SearchDep) -> HealthPublic:
    search_ok = await search.health()

    components = [
        ComponentPublic(
            name="catalog",
            status="ok",
            detail=f"{len(catalog)} dishes loaded",
        ),
        ComponentPublic(
            name="search",
            status="ok" if search_ok else "unavailable",
            detail=None if search_ok else "Meilisearch unreachable; /api/search returns 503.",
        ),
    ]
    return HealthPublic(
        status="ok" if search_ok else "degraded",
        version=__version__,
        dishes=list(catalog.slugs),
        components=components,
    )
