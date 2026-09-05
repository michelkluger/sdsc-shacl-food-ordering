"""Read a SHACL node shape into plain Python structures.

This module is the only place that knows the shape of the RDF. Everything downstream - the
JSON Schema, the UI schema, the JSON-LD context, the price calculation, the error pointers -
consumes :class:`PropertyConstraints` and never touches an rdflib graph again.

Keeping the graph queries in one file is what makes "add a dish by adding two files" true:
a new shape is understood by the same reader, so no other module has to change.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from rdflib import RDF, RDFS, Graph, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import SH, XSD
from rdflib.term import Node

from food_api.namespaces import FOOD

# Datatypes we are willing to put in a form. Anything else is a modelling mistake we would
# rather surface loudly than render as a broken control.
SUPPORTED_DATATYPES: frozenset[URIRef] = frozenset(
    {
        XSD.string,
        XSD.integer,
        XSD.decimal,
        XSD.double,
        XSD.float,
        XSD.boolean,
        XSD.date,
        XSD.dateTime,
        XSD.time,
    }
)


class ShapeError(RuntimeError):
    """A shape could not be read as a form definition."""


@dataclass(frozen=True, slots=True)
class OptionTerm:
    """One selectable value, taken from a ``sh:in`` list and labelled from the vocabulary."""

    iri: str
    token: str
    label: str
    surcharge: Decimal = Decimal(0)
    allergens: tuple[str, ...] = ()
    excluded_by_diet: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PropertyGroup:
    """A ``sh:PropertyGroup``, which becomes a JSON Forms ``Group`` in the UI schema."""

    iri: str
    label: str
    order: Decimal


@dataclass(frozen=True, slots=True)
class PropertyConstraints:
    """The constraints of a single ``sh:PropertyShape``, flattened for consumption."""

    path: str
    name: str
    label: str | None = None
    description: str | None = None
    datatype: str | None = None
    node_kind: str | None = None
    min_count: int | None = None
    max_count: int | None = None
    options: tuple[OptionTerm, ...] = ()
    min_inclusive: Decimal | None = None
    max_inclusive: Decimal | None = None
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None
    default: Any = None
    group: PropertyGroup | None = None
    order: Decimal | None = None
    message: str | None = None

    @property
    def is_required(self) -> bool:
        return (self.min_count or 0) >= 1

    @property
    def is_multi_valued(self) -> bool:
        """True when the property may hold more than one value, so JSON models it as an array."""
        return self.max_count is None or self.max_count > 1

    @property
    def is_enumerated(self) -> bool:
        return bool(self.options)


def _localname(iri: str) -> str:
    for sep in ("#", "/"):
        if sep in iri:
            head, _, tail = iri.rpartition(sep)
            if tail:
                return tail
            del head
    return iri


def _scalar(value: Node | None) -> Any:
    """Convert an rdflib term to the Python value we want in JSON."""
    if value is None:
        return None
    if isinstance(value, Literal):
        return value.toPython()
    if isinstance(value, URIRef):
        return _localname(str(value))
    return str(value)


def _one(graph: Graph, subject: Node, predicate: URIRef) -> Node | None:
    return graph.value(subject=subject, predicate=predicate)


def _int(graph: Graph, subject: Node, predicate: URIRef) -> int | None:
    raw = _one(graph, subject, predicate)
    return int(raw) if isinstance(raw, Literal) else None  # ty: ignore[invalid-argument-type]


def _decimal(graph: Graph, subject: Node, predicate: URIRef) -> Decimal | None:
    raw = _one(graph, subject, predicate)
    return Decimal(str(raw)) if isinstance(raw, Literal) else None


def _label(graph: Graph, subject: Node, fallback: str) -> str:
    for label in graph.objects(subject, RDFS.label):
        return str(label)
    return fallback


def _strings(graph: Graph, subject: Node, predicate: URIRef) -> tuple[str, ...]:
    return tuple(sorted(str(value) for value in graph.objects(subject, predicate)))


def _read_option(graph: Graph, term: Node) -> OptionTerm:
    iri = str(term)
    token = _localname(iri)
    return OptionTerm(
        iri=iri,
        token=token,
        label=_label(graph, term, token),
        surcharge=_decimal(graph, term, FOOD.surcharge) or Decimal(0),
        allergens=_strings(graph, term, FOOD.containsAllergen),
        excluded_by_diet=_strings(graph, term, FOOD.excludedByDiet),
    )


def _read_in_list(graph: Graph, property_shape: Node) -> tuple[OptionTerm, ...]:
    head = _one(graph, property_shape, SH["in"])
    if head is None:
        return ()
    members = list(Collection(graph, head))  # ty: ignore[invalid-argument-type]
    return tuple(_read_option(graph, member) for member in members)


def _read_group(graph: Graph, property_shape: Node) -> PropertyGroup | None:
    group = _one(graph, property_shape, SH.group)
    if group is None:
        return None
    iri = str(group)
    return PropertyGroup(
        iri=iri,
        label=_label(graph, group, _localname(iri)),
        order=_decimal(graph, group, SH.order) or Decimal(0),
    )


def _read_property(graph: Graph, property_shape: Node) -> PropertyConstraints:
    path = _one(graph, property_shape, SH.path)
    if not isinstance(path, URIRef):
        raise ShapeError(
            f"Property shape {property_shape} has no simple IRI sh:path. "
            "Sequence, alternative and inverse paths are not supported by the form translator."
        )

    # `sh:name` is read as the *field identifier* here, not as a display label. The SHACL spec
    # intends it as a human-readable name, but a form needs one stable token that is at once the
    # JSON key, the JSON-LD term and the error pointer, and `sh:name` is the only per-property
    # naming slot SHACL offers. `rdfs:label` supplies the display title instead. The deviation
    # is deliberate and written up in DESIGN.md.
    name_literal = _one(graph, property_shape, SH.name)
    name = str(name_literal) if name_literal is not None else _localname(str(path))
    label_literal = _one(graph, property_shape, RDFS.label)

    datatype = _one(graph, property_shape, SH.datatype)
    if isinstance(datatype, URIRef) and datatype not in SUPPORTED_DATATYPES:
        raise ShapeError(f"Property shape for {name!r} uses unsupported datatype {datatype}.")

    node_kind = _one(graph, property_shape, SH.nodeKind)
    description = _one(graph, property_shape, SH.description)
    message = _one(graph, property_shape, SH.message)

    return PropertyConstraints(
        path=str(path),
        name=name,
        label=str(label_literal) if label_literal is not None else None,
        description=str(description) if description is not None else None,
        datatype=str(datatype) if datatype is not None else None,
        node_kind=str(node_kind) if node_kind is not None else None,
        min_count=_int(graph, property_shape, SH.minCount),
        max_count=_int(graph, property_shape, SH.maxCount),
        options=_read_in_list(graph, property_shape),
        min_inclusive=_decimal(graph, property_shape, SH.minInclusive),
        max_inclusive=_decimal(graph, property_shape, SH.maxInclusive),
        min_length=_int(graph, property_shape, SH.minLength),
        max_length=_int(graph, property_shape, SH.maxLength),
        pattern=str(_one(graph, property_shape, SH.pattern) or "") or None,
        default=_scalar(_one(graph, property_shape, SH.defaultValue)),
        group=_read_group(graph, property_shape),
        order=_decimal(graph, property_shape, SH.order),
        message=str(message) if message is not None else None,
    )


def find_node_shape(graph: Graph) -> URIRef:
    """Return the single ``sh:NodeShape`` a dish shape file declares.

    A dish contributes exactly one order shape. Enforcing that here turns a modelling slip into
    a clear startup error rather than a form that silently drops half its fields.
    """
    candidates = sorted(
        {
            subject
            for subject in graph.subjects(RDF.type, SH.NodeShape)
            if isinstance(subject, URIRef) and (subject, SH.property, None) in graph
        },
        key=str,
    )
    if not candidates:
        raise ShapeError("No sh:NodeShape with sh:property found in the dish shape.")
    if len(candidates) > 1:
        names = ", ".join(str(candidate) for candidate in candidates)
        raise ShapeError(f"Expected exactly one order node shape, found {len(candidates)}: {names}")
    return candidates[0]


def read_properties(graph: Graph, node_shape: URIRef) -> tuple[PropertyConstraints, ...]:
    """Read every ``sh:property`` of ``node_shape``, ordered for display.

    Property shapes reached by IRI (the reusable ones in ``shapes/common.ttl``) and property
    shapes written inline as blank nodes are treated identically - that is the whole point of
    letting SHACL, rather than Python, decide what a dish's form contains.
    """
    properties = [
        _read_property(graph, property_shape)
        for property_shape in graph.objects(node_shape, SH.property)
    ]

    seen: dict[str, str] = {}
    for prop in properties:
        if prop.name in seen:
            raise ShapeError(
                f"Two property shapes claim the JSON key {prop.name!r} "
                f"({seen[prop.name]} and {prop.path}). sh:name must be unique within a shape."
            )
        seen[prop.name] = prop.path

    def sort_key(prop: PropertyConstraints) -> tuple[Decimal, Decimal, str]:
        group_order = prop.group.order if prop.group else Decimal(9999)
        return (group_order, prop.order if prop.order is not None else Decimal(9999), prop.name)

    properties.sort(key=sort_key)
    return tuple(properties)
