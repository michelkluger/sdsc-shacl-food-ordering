"""Project the dish catalogue into Meilisearch documents.

The documents are built from the loaded catalogue, including the option labels pulled out of
the SHACL shapes. A dish added as two data files is therefore searchable - by name, by cuisine,
by allergen, and by the name of any option it offers - without anyone writing an indexing rule
for it.
"""

from __future__ import annotations

from typing import Any

from food_api.catalog.registry import Catalog, Dish


def dish_document(dish: Dish) -> dict[str, Any]:
    """Build the search document for one dish."""
    option_labels = sorted({option.label for prop in dish.properties for option in prop.options})
    allergens = sorted(
        set(dish.summary.allergens)
        | {
            allergen
            for prop in dish.properties
            for option in prop.options
            for allergen in option.allergens
        }
    )

    return {
        "slug": dish.slug,
        "name": dish.summary.name,
        "description": dish.summary.description,
        "cuisine": dish.summary.cuisine,
        "basePrice": float(dish.summary.base_price),
        "currency": dish.summary.currency,
        "image": dish.summary.image,
        "tags": list(dish.summary.tags),
        "diets": list(dish.summary.diets),
        # Allergens are the union of the dish's own and every option it offers, so a search for
        # "nuts" surfaces a dish whose only nut is an optional topping. Over-reporting is the
        # right direction to err in for an allergen.
        "allergens": allergens,
        "optionLabels": option_labels,
        "fieldCount": len(dish.properties),
    }


def catalog_documents(catalog: Catalog) -> list[dict[str, Any]]:
    """Build the search documents for every dish in the catalogue."""
    return [dish_document(dish) for dish in catalog.list_dishes()]
