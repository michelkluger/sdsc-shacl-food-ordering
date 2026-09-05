"""Tests that need a real Meilisearch.

The rest of the suite runs against :class:`InMemorySearch`, which is a substring matcher. That
is enough to test routing and error handling, but it cannot tell us whether the index settings
are right, whether filters use the correct syntax, or whether Meilisearch's typo tolerance
actually finds a dish. Those need the real thing, so they live here behind a marker.

Skipped when nothing answers at ``FOOD_API_MEILI_URL``; always run in CI, where the workflow
starts Meilisearch as a service container.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import suppress

import pytest
from meilisearch_python_sdk import AsyncClient
from meilisearch_python_sdk.errors import MeilisearchError

from food_api.catalog.registry import Catalog
from food_api.config import Settings
from food_api.search.client import MeilisearchSearch
from food_api.search.indexer import catalog_documents

pytestmark = pytest.mark.integration


@pytest.fixture
async def live_search(
    settings: Settings,
    catalog: Catalog,
) -> AsyncIterator[MeilisearchSearch]:
    """A Meilisearch client pointed at a throwaway index, seeded with the real catalogue.

    A unique index per test keeps a failure from leaving state behind that makes the next run
    pass or fail for the wrong reason, and the index is dropped afterwards so a CI service
    container is not slowly filled with orphans.
    """
    index_name = f"dishes_test_{uuid.uuid4().hex[:8]}"
    client = AsyncClient(
        settings.meili_url,
        settings.meili_master_key,
        timeout=settings.meili_timeout_seconds,
    )
    search = MeilisearchSearch(client, index_name)
    try:
        if not await search.health():
            pytest.skip(f"No Meilisearch at {settings.meili_url}")

        await search.index_dishes(catalog_documents(catalog))
        yield search
    finally:
        with suppress(MeilisearchError, OSError):
            await client.index(index_name).delete()
        await search.aclose()


async def test_health_reports_true_against_a_live_server(live_search: MeilisearchSearch) -> None:
    assert await live_search.health() is True


async def test_full_text_search_finds_a_dish(live_search: MeilisearchSearch) -> None:
    results = await live_search.search("noodles")
    assert "ramen" in {hit["slug"] for hit in results.hits}


async def test_search_tolerates_a_typo(live_search: MeilisearchSearch) -> None:
    """The reason for using a search engine rather than a substring match over the catalogue."""
    results = await live_search.search("ramenn")
    assert "ramen" in {hit["slug"] for hit in results.hits}


async def test_option_labels_are_searchable(live_search: MeilisearchSearch) -> None:
    results = await live_search.search("merguez")
    assert "french-tacos" in {hit["slug"] for hit in results.hits}


async def test_filterable_attributes_are_configured(live_search: MeilisearchSearch) -> None:
    """Filtering fails outright unless the attribute was declared filterable at index time."""
    results = await live_search.search("", filters=["cuisine = 'Japanese'"])
    assert {hit["slug"] for hit in results.hits} == {"ramen"}


def _facet_keys(results: object) -> set[str]:
    return set(getattr(results, "facets", {}))


async def test_facets_come_back_for_every_filterable_attribute(
    live_search: MeilisearchSearch,
) -> None:
    results = await live_search.search("")
    assert {"cuisine", "diets", "allergens", "tags"} <= _facet_keys(results)


async def test_seeding_twice_is_idempotent(
    live_search: MeilisearchSearch,
    catalog: Catalog,
) -> None:
    """Setup, CI and startup may all seed; running it again must change nothing."""
    documents = catalog_documents(catalog)
    before = (await live_search.search("")).estimated_total

    await live_search.index_dishes(documents)
    after = (await live_search.search("")).estimated_total

    assert before == after == len(documents)
