"""Response models.

These describe the *envelopes* the API returns. The interesting payloads inside them - the JSON
Forms schema, the UI schema, the JSON-LD context - are deliberately typed as open dictionaries:
they are generated from SHACL at runtime, so pinning their structure in Pydantic would mean
maintaining a second, weaker copy of the shape language.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DishSummaryModel(BaseModel):
    """A dish as it appears in a menu listing or a search hit."""

    model_config = ConfigDict(populate_by_name=True)

    slug: str
    name: str
    description: str
    cuisine: str
    base_price: float = Field(alias="basePrice")
    currency: str
    image: str | None = None
    tags: list[str] = Field(default_factory=list)
    diets: list[str] = Field(default_factory=list)
    allergens: list[str] = Field(default_factory=list)


class FormResponse(BaseModel):
    """Everything needed to render one dish's order form.

    ``schema_`` and ``uischema`` are what JSON Forms consumes. ``context`` is included so a
    JSON-LD-aware client can round-trip the same submission into RDF itself - the browser does
    not need it, but publishing it keeps the contract honest about what the server will do
    with the payload.
    """

    model_config = ConfigDict(populate_by_name=True)

    dish: DishSummaryModel
    json_schema: dict[str, Any] = Field(alias="schema")
    uischema: dict[str, Any]
    context: dict[str, Any] = Field(alias="@context")
    shape_iri: str = Field(alias="shapeIri")


class OrderRequest(BaseModel):
    """The body of a submission.

    ``data`` is intentionally unvalidated by Pydantic: SHACL is the validator, and letting
    Pydantic reject a payload first would produce errors in a different shape from the SHACL
    ones and hide the very failures this service exists to report.
    """

    data: dict[str, Any] = Field(default_factory=dict)


class OrderReceipt(BaseModel):
    """Confirmation of an order that passed validation."""

    model_config = ConfigDict(populate_by_name=True)

    order_id: str = Field(alias="orderId")
    dish: str
    accepted: bool = True
    total: float
    currency: str
    data: dict[str, Any]


class ComponentHealth(BaseModel):
    name: str
    status: str
    detail: str | None = None


class HealthResponse(BaseModel):
    """Service health. ``degraded`` means usable but with search switched off."""

    status: str
    version: str
    dishes: list[str]
    components: list[ComponentHealth]


class SearchResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    query: str
    hits: list[dict[str, Any]]
    estimated_total: int = Field(alias="estimatedTotal")
    facets: dict[str, dict[str, int]] = Field(default_factory=dict)
