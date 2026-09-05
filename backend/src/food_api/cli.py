"""Operational commands.

The setup scripts are deliberately thin wrappers around this module. Anything with real logic -
waiting for Meilisearch, seeding it, checking the corpus parses - lives here in Python where it
is testable and identical on every platform, rather than being written twice in bash and
PowerShell and drifting apart.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from typing import Annotated

import typer
from meilisearch_python_sdk import AsyncClient

from food_api import __version__
from food_api.catalog.registry import Catalog, CatalogError
from food_api.config import Settings, get_settings
from food_api.search.client import MeilisearchSearch, SearchUnavailableError
from food_api.search.indexer import catalog_documents

app = typer.Typer(
    name="food-api",
    help="Operational commands for the SHACL-driven food ordering API.",
    no_args_is_help=True,
    add_completion=False,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
logger = logging.getLogger("food_api.cli")


def _search(settings: Settings) -> MeilisearchSearch:
    client = AsyncClient(
        settings.meili_url,
        settings.meili_master_key,
        timeout=settings.meili_timeout_seconds,
    )
    return MeilisearchSearch(client, settings.meili_index)


def _load_catalog(settings: Settings) -> Catalog:
    try:
        return Catalog(settings).load()
    except CatalogError as exc:
        typer.secho(f"Dish corpus is invalid: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc


@app.command()
def version() -> None:
    """Print the package version."""
    typer.echo(__version__)


@app.command()
def check() -> None:
    """Parse every dish and print what was derived from it.

    Run this after adding a dish: it exercises exactly the code path the server runs at startup,
    so a shape that will not load fails here instead of at the first request.
    """
    settings = get_settings()
    catalog = _load_catalog(settings)

    typer.secho(f"{len(catalog)} dishes loaded from {settings.dishes_dir}", fg=typer.colors.GREEN)
    for dish in catalog.list_dishes():
        required = sorted(dish.form.schema.get("required", []))
        typer.echo(
            f"  {dish.slug:<16} {len(dish.properties):>2} fields  "
            f"{len(required):>2} required  shape={dish.node_shape.split('#')[-1]}"
        )


@app.command()
def form(slug: Annotated[str, typer.Argument(help="Dish slug, e.g. `ramen`.")]) -> None:
    """Print a dish's generated JSON Forms schema pair and JSON-LD context."""
    catalog = _load_catalog(get_settings())
    dish = catalog.get(slug)
    if dish is None:
        typer.secho(
            f"Unknown dish {slug!r}. Available: {', '.join(catalog.slugs)}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    typer.echo(
        json.dumps(
            {
                "schema": dish.form.schema,
                "uischema": dish.form.uischema,
                "@context": dish.form.context,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


@app.command("wait-for-search")
def wait_for_search(
    timeout: Annotated[int, typer.Option(help="Seconds to wait before giving up.")] = 60,
    interval: Annotated[float, typer.Option(help="Seconds between attempts.")] = 1.0,
) -> None:
    """Block until Meilisearch answers its health endpoint, or exit non-zero on timeout."""
    settings = get_settings()

    async def _wait() -> bool:
        search = _search(settings)
        deadline = time.monotonic() + timeout
        attempt = 0
        while time.monotonic() < deadline:
            attempt += 1
            if await search.health():
                logger.info("Meilisearch is ready at %s (attempt %d)", settings.meili_url, attempt)
                return True
            await asyncio.sleep(interval)
        return False

    if not asyncio.run(_wait()):
        typer.secho(
            f"Meilisearch at {settings.meili_url} did not become ready within {timeout}s.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)


@app.command()
def seed() -> None:
    """Index every dish into Meilisearch.

    Idempotent: it upserts by slug and re-applies the index settings, so running it after
    adding a dish is the whole of "make the new dish searchable".
    """
    settings = get_settings()
    catalog = _load_catalog(settings)
    documents = catalog_documents(catalog)

    async def _seed() -> None:
        await _search(settings).index_dishes(documents)

    try:
        asyncio.run(_seed())
    except SearchUnavailableError as exc:
        typer.secho(f"Could not seed Meilisearch: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    typer.secho(
        f"Indexed {len(documents)} dishes into '{settings.meili_index}' at {settings.meili_url}",
        fg=typer.colors.GREEN,
    )


@app.command()
def bootstrap(
    timeout: Annotated[int, typer.Option(help="Seconds to wait for Meilisearch.")] = 60,
) -> None:
    """Validate the corpus, wait for Meilisearch, and seed it. Used by the setup scripts."""
    check()
    wait_for_search(timeout=timeout)
    seed()
    typer.secho("Bootstrap complete.", fg=typer.colors.GREEN)


def main() -> None:
    sys.exit(app())


if __name__ == "__main__":
    main()
