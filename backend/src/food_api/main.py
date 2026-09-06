"""FastAPI application factory and lifespan."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from meilisearch_python_sdk import AsyncClient

from food_api import __version__
from food_api.api.main import api_router
from food_api.catalog.registry import Catalog
from food_api.core.config import Settings, get_settings
from food_api.core.errors import register_exception_handlers
from food_api.search.client import MeilisearchSearch, SearchPort

logger = logging.getLogger(__name__)

API_PREFIX = "/api"

DESCRIPTION = """
A food-ordering API whose form logic lives entirely in **JSON-LD documents and SHACL shapes**.

* `GET /api/dishes/{slug}/form` returns a JSON Forms schema pair generated from the dish's
  SHACL shape at startup - no form definition is written by hand.
* `POST /api/orders/{slug}` lifts the submitted payload into RDF using the same generated
  JSON-LD context and validates it with pySHACL, returning violations addressed by JSON pointer.
* Adding a dish means adding `dish.jsonld` and `shape.ttl`. There is no code to change.
"""


def _build_search(settings: Settings) -> SearchPort:
    client = AsyncClient(
        settings.meili_url,
        settings.meili_master_key,
        timeout=settings.meili_timeout_seconds,
    )
    return MeilisearchSearch(client, settings.meili_index)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Load the dish corpus, then check on search.

    The corpus is loaded eagerly and a failure here is fatal: a service that cannot parse its
    own shapes has nothing useful to offer, and finding out at startup beats finding out on the
    first order. Search is checked but not required - see ``require_search``.
    """
    settings: Settings = app.state.settings
    app.state.catalog = Catalog(settings).load()

    # Only close a client we created ourselves. An injected one belongs to the caller - a test
    # reusing a fixture across requests would otherwise get a closed pool on the second app.
    owns_search = not hasattr(app.state, "search")
    if owns_search:
        app.state.search = _build_search(settings)

    if await app.state.search.health():
        logger.info("Meilisearch reachable at %s", settings.meili_url)
    elif settings.require_search:
        raise RuntimeError(
            f"Meilisearch at {settings.meili_url} is unreachable "
            "and FOOD_API_REQUIRE_SEARCH is set."
        )
    else:
        logger.warning(
            "Meilisearch at %s is unreachable. /api/search will return 503; "
            "dishes, forms and orders are unaffected.",
            settings.meili_url,
        )

    try:
        yield
    finally:
        if owns_search:
            await app.state.search.aclose()


def create_app(
    settings: Settings | None = None,
    *,
    search: SearchPort | None = None,
) -> FastAPI:
    """Build the application.

    ``settings`` and ``search`` are injectable so tests can point the catalogue at a fixture
    corpus and swap in an in-memory search without patching module globals.
    """
    settings = settings or get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=DESCRIPTION,
        lifespan=lifespan,
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
    )
    app.state.settings = settings
    if search is not None:
        app.state.search = search

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    register_exception_handlers(app)

    app.include_router(api_router, prefix=API_PREFIX)

    return app


app = create_app()
