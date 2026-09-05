"""Search access, behind a port.

The API depends on :class:`SearchPort`, never on Meilisearch directly. That buys two things:
the unit and API test suites run with :class:`InMemorySearch` and need no container, and an
unreachable Meilisearch degrades one endpoint instead of taking the service down.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, cast, runtime_checkable

from meilisearch_python_sdk import AsyncClient
from meilisearch_python_sdk.errors import MeilisearchError
from meilisearch_python_sdk.models.settings import FilterableAttributes

if TYPE_CHECKING:
    from meilisearch_python_sdk.types import Filter

logger = logging.getLogger(__name__)

#: Attributes a query text is matched against, most significant first.
SEARCHABLE_ATTRIBUTES: list[str] = ["name", "description", "cuisine", "tags", "optionLabels"]

#: Attributes usable in `filter=` expressions and returned as facet counts. Typed with the
#: SDK's own union because `list` is invariant: a plain `list[str]` is not assignable to the
#: `list[str | FilterableAttributes]` the client expects.
FILTERABLE_ATTRIBUTES: list[str | FilterableAttributes] = [
    "cuisine",
    "diets",
    "allergens",
    "tags",
]

#: The same names as plain strings, for the facet request and for the in-memory backend.
FACET_NAMES: list[str] = [str(attribute) for attribute in FILTERABLE_ATTRIBUTES]

SORTABLE_ATTRIBUTES: list[str] = ["basePrice", "name"]


class SearchUnavailableError(RuntimeError):
    """The search backend could not be reached."""


@dataclass(frozen=True, slots=True)
class SearchResults:
    """A page of search hits plus the facet counts for the same query."""

    hits: list[dict[str, Any]]
    query: str
    estimated_total: int
    facets: dict[str, dict[str, int]] = field(default_factory=dict)


@runtime_checkable
class SearchPort(Protocol):
    """What the API needs from a search backend."""

    async def health(self) -> bool: ...

    async def index_dishes(self, documents: list[dict[str, Any]]) -> None: ...

    async def aclose(self) -> None: ...

    async def search(
        self,
        query: str,
        *,
        filters: list[str] | None = None,
        limit: int = 20,
    ) -> SearchResults: ...


class MeilisearchSearch:
    """:class:`SearchPort` backed by Meilisearch."""

    def __init__(self, client: AsyncClient, index_name: str) -> None:
        self._client = client
        self._index_name = index_name

    async def aclose(self) -> None:
        """Release the underlying HTTP connection pool."""
        await self._client.aclose()

    async def health(self) -> bool:
        try:
            await self._client.health()
        except (MeilisearchError, OSError) as exc:
            logger.warning("Meilisearch health check failed: %s", exc)
            return False
        return True

    async def index_dishes(self, documents: list[dict[str, Any]]) -> None:
        """Create or update the index, apply its settings, and upsert every dish.

        Idempotent by design: seeding is run by the setup script, by CI, and optionally at
        startup, and running it twice must be indistinguishable from running it once.
        """
        try:
            index = await self._client.create_index(self._index_name, primary_key="slug")
        except MeilisearchError:
            # Already exists, which is the normal case on every run after the first.
            index = self._client.index(self._index_name)

        try:
            await index.update_searchable_attributes(SEARCHABLE_ATTRIBUTES)
            await index.update_filterable_attributes(FILTERABLE_ATTRIBUTES)
            await index.update_sortable_attributes(SORTABLE_ATTRIBUTES)
            task = await index.add_documents(documents)
            await self._client.wait_for_task(task.task_uid)
        except (MeilisearchError, OSError) as exc:
            raise SearchUnavailableError(f"Could not index dishes: {exc}") from exc

    async def search(
        self,
        query: str,
        *,
        filters: list[str] | None = None,
        limit: int = 20,
    ) -> SearchResults:
        index = self._client.index(self._index_name)
        try:
            result = await index.search(
                query or "",
                limit=limit,
                # Widened to the SDK's `Filter` alias (`str | list[str | list[str]]`);
                # a bare `list[str]` does not satisfy it because `list` is invariant.
                filter=cast("Filter | None", list(filters) if filters else None),
                facets=FACET_NAMES,
            )
        except (MeilisearchError, OSError) as exc:
            raise SearchUnavailableError(f"Search request failed: {exc}") from exc

        return SearchResults(
            hits=list(result.hits),
            query=query,
            estimated_total=result.estimated_total_hits or len(result.hits),
            facets=dict(result.facet_distribution or {}),
        )


class InMemorySearch:
    """A :class:`SearchPort` that keeps documents in a list.

    Substring matching, not Meilisearch's typo-tolerant ranking - it exists so the API suite
    can assert routing, filtering and error handling without a container. Anything that depends
    on real relevance is covered by the integration tests instead.
    """

    def __init__(self, documents: list[dict[str, Any]] | None = None) -> None:
        self.documents: list[dict[str, Any]] = list(documents or [])
        self.available = True

    async def aclose(self) -> None:
        """Nothing to release. Present so the fake satisfies the whole port."""

    async def health(self) -> bool:
        return self.available

    async def index_dishes(self, documents: list[dict[str, Any]]) -> None:
        if not self.available:
            raise SearchUnavailableError("In-memory search marked unavailable.")
        by_slug = {document["slug"]: document for document in self.documents}
        for document in documents:
            by_slug[document["slug"]] = document
        self.documents = [by_slug[slug] for slug in sorted(by_slug)]

    async def search(
        self,
        query: str,
        *,
        filters: list[str] | None = None,
        limit: int = 20,
    ) -> SearchResults:
        if not self.available:
            raise SearchUnavailableError("In-memory search marked unavailable.")

        needle = query.strip().lower()
        hits = [
            document for document in self.documents if not needle or needle in _haystack(document)
        ]
        for expression in filters or []:
            attribute, _, wanted = expression.partition(" = ")
            wanted = wanted.strip("'\"")
            hits = [hit for hit in hits if wanted in _as_values(hit.get(attribute.strip()))]

        facets = {attribute: _count(hits, attribute) for attribute in FACET_NAMES}
        return SearchResults(
            hits=hits[:limit],
            query=query,
            estimated_total=len(hits),
            facets=facets,
        )


def _haystack(document: dict[str, Any]) -> str:
    parts: list[str] = []
    for attribute in SEARCHABLE_ATTRIBUTES:
        parts.extend(_as_values(document.get(attribute)))
    return " ".join(parts).lower()


def _as_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _count(hits: list[dict[str, Any]], attribute: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for hit in hits:
        for value in _as_values(hit.get(attribute)):
            counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))
