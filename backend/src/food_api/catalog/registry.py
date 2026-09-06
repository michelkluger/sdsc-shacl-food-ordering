"""Discover dishes on disk and build everything derived from them, once, at startup.

A dish is a directory under ``data/dishes/`` containing exactly two files::

    data/dishes/<slug>/dish.jsonld   the catalogue entry (name, price, tags, allergens)
    data/dishes/<slug>/shape.ttl     the SHACL order shape

Nothing else registers a dish. There is no list of dishes in Python, no enum, no route per
dish - the filesystem is the registry. That is what makes "add a third dish without touching
code" a property of the design rather than a claim in a README.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from decimal import Decimal
from functools import cached_property
from pathlib import Path
from typing import Any

from rdflib import Graph, URIRef

from food_api.core.config import Settings
from food_api.shacl.introspect import (
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES,
    PropertyConstraints,
    ShapeError,
    find_node_shape,
    read_properties,
)
from food_api.shacl.jsonforms import FormDefinition, build_form

logger = logging.getLogger(__name__)

DISH_DOCUMENT = "dish.jsonld"
SHAPE_DOCUMENT = "shape.ttl"


class CatalogError(RuntimeError):
    """The dish corpus on disk could not be loaded."""


@dataclass(frozen=True, slots=True)
class DishSummary:
    """The catalogue half of a dish: what a menu or a search result shows, in one language."""

    slug: str
    name: str
    description: str
    cuisine: str
    base_price: Decimal
    currency: str
    image: str | None
    tags: tuple[str, ...]
    diets: tuple[str, ...]
    allergens: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "name": self.name,
            "description": self.description,
            "cuisine": self.cuisine,
            "basePrice": float(self.base_price),
            "currency": self.currency,
            "image": self.image,
            "tags": list(self.tags),
            "diets": list(self.diets),
            "allergens": list(self.allergens),
        }


@dataclass(frozen=True, slots=True)
class Dish:
    """A dish: its catalogue entry, its shapes graph, and everything derived from them.

    Forms and summaries are built once per supported language at startup. The translation is
    pure and the corpus is read-only, so there is nothing to recompute per request - a German
    form costs the same as an English one.
    """

    summaries: dict[str, DishSummary]
    node_shape: URIRef
    properties: tuple[PropertyConstraints, ...]
    forms: dict[str, FormDefinition]
    #: Shapes graph for this dish only: shared property shapes + this dish's shape + vocabulary.
    shapes_graph: Graph
    #: The shared vocabulary. Merged into the *data* graph so SPARQL constraints can read it.
    vocabulary: Graph

    @property
    def slug(self) -> str:
        return self.summary.slug

    @property
    def summary(self) -> DishSummary:
        """The default-language summary. Prefer :meth:`summary_for` in a request path."""
        return self.summaries[DEFAULT_LANGUAGE]

    @property
    def form(self) -> FormDefinition:
        """The default-language form.

        Validation uses this one deliberately: `key_by_path`, `token_by_iri` and `surcharges`
        are language-independent by construction, so error mapping and pricing never depend on
        which language the client happens to be reading in.
        """
        return self.forms[DEFAULT_LANGUAGE]

    def summary_for(self, language: str) -> DishSummary:
        return self.summaries.get(language, self.summaries[DEFAULT_LANGUAGE])

    def form_for(self, language: str) -> FormDefinition:
        return self.forms.get(language, self.forms[DEFAULT_LANGUAGE])


def _as_list(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, list):
        return tuple(str(item) for item in value)
    return (str(value),)


def _localised(value: Any, language: str) -> str:
    """Read a JSON-LD language map, or a plain string.

    ``dish.jsonld`` may write either::

        "name": "Ramen"
        "name": { "@none": "Ramen", "de": "Ramen", "fr": "Ramen japonais" }

    A plain string is the right choice for a proper noun that is the same everywhere, and the
    map for anything that genuinely differs. ``@none`` is the JSON-LD spelling of "no language",
    and serves as the fallback.
    """
    if isinstance(value, dict):
        base = language.partition("-")[0].lower()
        for key in (language.lower(), base, DEFAULT_LANGUAGE, "@none"):
            found = value.get(key)
            if isinstance(found, str):
                return found
        for found in value.values():
            if isinstance(found, str):
                return found
        return ""
    return str(value)


def _read_summary(slug: str, document: dict[str, Any], language: str) -> DishSummary:
    """Read the catalogue fields out of a dish's JSON-LD document, in one language.

    The document is read as JSON rather than through the graph on purpose: these are flat
    presentation fields with no constraints attached, and going via RDF would buy nothing but
    a round trip. The *shape* is where the semantics live.
    """
    try:
        return DishSummary(
            slug=slug,
            name=_localised(document["name"], language),
            description=_localised(document["description"], language),
            cuisine=_localised(document.get("cuisine", "Unspecified"), language),
            base_price=Decimal(str(document["basePrice"])),
            currency=document.get("currency", "CHF"),
            image=document.get("image"),
            tags=_as_list(document.get("tag")),
            diets=_as_list(document.get("diet")),
            allergens=_as_list(document.get("allergen")),
        )
    except KeyError as exc:
        raise CatalogError(
            f"{slug}/{DISH_DOCUMENT} is missing required key {exc.args[0]!r}"
        ) from exc


class Catalog:
    """The loaded dish corpus. Built once at startup and then read-only."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._dishes: dict[str, Dish] = {}

    @cached_property
    def base_context(self) -> dict[str, Any]:
        raw = json.loads(self._settings.base_context_path.read_text(encoding="utf-8"))
        context = raw.get("@context")
        if not isinstance(context, dict):
            raise CatalogError(f"{self._settings.base_context_path} has no object-valued @context.")
        return context

    @cached_property
    def vocabulary(self) -> Graph:
        """The shared vocabulary graph.

        It is merged into the *data* graph at validation time, not passed as pyshacl's
        ``ont_graph``: SPARQL constraints are evaluated against the data graph alone, so a rule
        that reads ``food:excludedByDiet`` only sees it if the vocabulary is genuinely there.
        """
        graph = Graph()
        graph.parse(self._settings.vocab_path, format="turtle")
        return graph

    @cached_property
    def _common_shapes(self) -> Graph:
        graph = Graph()
        graph.parse(self._settings.common_shapes_path, format="turtle")
        return graph

    @cached_property
    def translations(self) -> Graph:
        """Every ``data/i18n/<lang>.ttl`` file, merged.

        These carry nothing but language-tagged ``rdfs:label``, ``sh:description`` and
        ``sh:message`` literals attached to terms and property shapes that already exist. Adding
        a language is therefore adding one file - the same shape of change as adding a dish.
        """
        graph = Graph()
        directory = self._settings.i18n_dir
        if not directory.is_dir():
            logger.warning("No translations directory at %s; serving English only.", directory)
            return graph

        for path in sorted(directory.glob("*.ttl")):
            try:
                graph.parse(path, format="turtle")
            except Exception as exc:
                raise CatalogError(f"{path.name} is not valid Turtle: {exc}") from exc
        names = ", ".join(path.name for path in sorted(directory.glob("*.ttl")))
        logger.info("Loaded translations from %s", names or "(none)")
        return graph

    def load(self) -> Catalog:
        """Load every dish directory. Raises on the first malformed dish."""
        dishes_dir = self._settings.dishes_dir
        if not dishes_dir.is_dir():
            raise CatalogError(f"Dish directory {dishes_dir} does not exist.")

        for directory in sorted(p for p in dishes_dir.iterdir() if p.is_dir()):
            dish = self._load_dish(directory)
            self._dishes[dish.slug] = dish

        if not self._dishes:
            raise CatalogError(f"No dishes found under {dishes_dir}.")

        logger.info("Loaded %d dishes: %s", len(self._dishes), ", ".join(sorted(self._dishes)))
        return self

    def _load_dish(self, directory: Path) -> Dish:
        slug = directory.name
        document_path = directory / DISH_DOCUMENT
        shape_path = directory / SHAPE_DOCUMENT

        for path in (document_path, shape_path):
            if not path.is_file():
                raise CatalogError(f"Dish {slug!r} is missing {path.name}.")

        try:
            document = json.loads(document_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CatalogError(f"{slug}/{DISH_DOCUMENT} is not valid JSON: {exc}") from exc

        # Parse the dish's own shape first and in isolation, so `find_node_shape` looks only at
        # what this dish declares. The shared file contributes property shapes, never a node
        # shape, but relying on that by accident would be a trap for the next dish author.
        dish_shape = Graph()
        try:
            dish_shape.parse(shape_path, format="turtle")
        except Exception as exc:
            raise CatalogError(f"{slug}/{SHAPE_DOCUMENT} is not valid Turtle: {exc}") from exc

        shapes = Graph()
        shapes += dish_shape
        shapes += self._common_shapes
        # Labels, groups and option annotations live in the vocabulary; the shapes graph needs
        # them so the translator can name options and lay out groups.
        shapes += self.vocabulary
        # Translations attach language-tagged literals to those same subjects.
        shapes += self.translations

        try:
            node_shape = find_node_shape(dish_shape)
        except ShapeError as exc:
            raise CatalogError(f"Dish {slug!r}: {exc}") from exc

        summaries: dict[str, DishSummary] = {}
        forms: dict[str, FormDefinition] = {}
        properties_by_language: dict[str, tuple[PropertyConstraints, ...]] = {}

        for language in SUPPORTED_LANGUAGES:
            try:
                properties = read_properties(shapes, node_shape, language)
            except ShapeError as exc:
                raise CatalogError(f"Dish {slug!r} ({language}): {exc}") from exc

            summary = _read_summary(slug, document, language)
            summaries[language] = summary
            properties_by_language[language] = properties
            forms[language] = build_form(
                properties,
                base_context=self.base_context,
                title=summary.name,
                description=summary.description,
                language=language,
            )

        return Dish(
            summaries=summaries,
            node_shape=node_shape,
            properties=properties_by_language[DEFAULT_LANGUAGE],
            forms=forms,
            shapes_graph=shapes,
            vocabulary=self.vocabulary,
        )

    def __contains__(self, slug: object) -> bool:
        return slug in self._dishes

    def __len__(self) -> int:
        return len(self._dishes)

    @property
    def slugs(self) -> tuple[str, ...]:
        return tuple(sorted(self._dishes))

    def get(self, slug: str) -> Dish | None:
        return self._dishes.get(slug)

    def list_dishes(self) -> tuple[Dish, ...]:
        return tuple(self._dishes[slug] for slug in self.slugs)
