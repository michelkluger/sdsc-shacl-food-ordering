"""Shared fixtures.

Every fixture here is dish-agnostic on purpose. The contract suite parametrises over whatever
the catalogue discovered on disk, so a new dish is covered by the existing tests the moment its
files exist - the same property the production code claims.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from food_api.catalog.registry import Catalog, Dish
from food_api.config import Settings
from food_api.main import create_app
from food_api.search.client import InMemorySearch
from food_api.search.indexer import catalog_documents

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN = Path(__file__).parent / "golden"


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings()


@pytest.fixture(scope="session")
def catalog(settings: Settings) -> Catalog:
    """The real dish corpus, loaded once. Loading is pure and the result is read-only."""
    return Catalog(settings).load()


@pytest.fixture(scope="session")
def dish_slugs(catalog: Catalog) -> list[str]:
    return list(catalog.slugs)


@pytest.fixture
def search() -> InMemorySearch:
    return InMemorySearch()


@pytest.fixture
def seeded_search(catalog: Catalog) -> InMemorySearch:
    backend = InMemorySearch()
    backend.documents = catalog_documents(catalog)
    return backend


@pytest.fixture
async def client(settings: Settings, search: InMemorySearch) -> AsyncIterator[AsyncClient]:
    """An HTTP client speaking to the app in-process, with search stubbed out."""
    app = create_app(settings, search=search)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as http,
    ):
        yield http


@pytest.fixture
async def seeded_client(
    settings: Settings,
    seeded_search: InMemorySearch,
) -> AsyncIterator[AsyncClient]:
    app = create_app(settings, search=seeded_search)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as http,
    ):
        yield http


def load_fixture(slug: str, name: str) -> dict[str, Any]:
    """Read one order fixture, e.g. ``ramen/valid.json``."""
    return json.loads((FIXTURES / "orders" / slug / name).read_text(encoding="utf-8"))


def fixture_names(slug: str, prefix: str) -> list[str]:
    directory = FIXTURES / "orders" / slug
    if not directory.is_dir():
        return []
    return sorted(path.name for path in directory.glob(f"{prefix}*.json"))


@pytest.fixture
def valid_payload() -> Any:
    def _load(slug: str) -> dict[str, Any]:
        return load_fixture(slug, "valid.json")["data"]

    return _load


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Parametrise dish-agnostic tests over every dish found on disk.

    A test that asks for a ``dish`` argument is run once per dish in the corpus. This is what
    makes the "adding a dish requires no code change" claim testable rather than aspirational:
    the third dish gets the full contract suite without a line being added here.
    """
    if "dish" not in metafunc.fixturenames:
        return
    catalog = Catalog(Settings()).load()
    dishes: list[Dish] = list(catalog.list_dishes())
    metafunc.parametrize("dish", dishes, ids=[dish.slug for dish in dishes])


def iter_dish_slugs() -> Iterator[str]:
    yield from Catalog(Settings()).load().slugs
