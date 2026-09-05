"""Translate SHACL property constraints into a JSON Forms schema pair and a JSON-LD context.

Three artefacts come out of one pass over the same constraints:

``schema``
    JSON Schema draft-07, which JSON Forms uses to decide control types and to run its own
    optimistic client-side checks.
``uischema``
    The JSON Forms UI schema: groups, control order, and rendering options.
``context``
    The JSON-LD ``@context`` that lifts a submitted payload back into RDF.

Generating all three together is deliberate. The JSON key for a field is chosen once, from
``sh:name``, and is therefore identical in the form the browser renders, in the context that
lifts the answer, and in the JSON pointer that reports a violation. There is no second place
for the three to drift apart.

The generated JSON Schema is a *rendering hint*, not a security boundary: it cannot express the
``sh:sparql`` cross-field rules, so a payload that satisfies it may still be rejected. SHACL is
the authority - see ``shacl/validate.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from rdflib.namespace import XSD

from food_api.shacl.introspect import PropertyConstraints

#: Above this many options a dropdown beats a radio group.
_RADIO_MAX_OPTIONS = 3

#: Above this length a single-line text input stops being reasonable.
_MULTILINE_MIN_LENGTH = 120

#: Integer ranges no wider than this render as a slider rather than a spinner.
_SLIDER_MAX_SPAN = 10

_JSON_TYPES: dict[str, tuple[str, str | None]] = {
    str(XSD.string): ("string", None),
    str(XSD.integer): ("integer", None),
    str(XSD.decimal): ("number", None),
    str(XSD.double): ("number", None),
    str(XSD.float): ("number", None),
    str(XSD.boolean): ("boolean", None),
    str(XSD.date): ("string", "date"),
    str(XSD.dateTime): ("string", "date-time"),
    str(XSD.time): ("string", "time"),
}

_UNGROUPED = "__ungrouped__"

#: sh:nodeKind value meaning "this property points at an IRI, not a literal".
_SH_IRI = "http://www.w3.org/ns/shacl#IRI"


@dataclass(frozen=True, slots=True)
class FormDefinition:
    """Everything a client needs to render, submit and have errors mapped back."""

    schema: dict[str, Any]
    uischema: dict[str, Any]
    context: dict[str, Any]
    #: RDF predicate IRI -> JSON key. Used in reverse to turn a ``sh:resultPath`` into a pointer.
    key_by_path: dict[str, str] = field(default_factory=dict)
    #: Option IRI -> compact token, so a violation can report ``"chashu"`` and not a full IRI.
    token_by_iri: dict[str, str] = field(default_factory=dict)
    #: JSON key -> option token -> surcharge, for pricing a valid order.
    surcharges: dict[str, dict[str, Decimal]] = field(default_factory=dict)


def _number(value: Decimal) -> int | float:
    """Render a Decimal as the narrowest JSON number that round-trips it."""
    return int(value) if value == value.to_integral_value() else float(value)


def _value_schema(prop: PropertyConstraints) -> dict[str, Any]:
    """The schema for a *single* value, before array wrapping."""
    if prop.is_enumerated:
        # `oneOf` with const/title rather than a bare `enum`: it is the only draft-07 construct
        # JSON Forms renders with human labels, and the labels come from rdfs:label in the
        # vocabulary, so a term is named once and every dish that offers it inherits the name.
        return {
            "type": "string",
            "oneOf": [
                {"const": option.token, "title": option.label} for option in prop.options
            ],
        }

    json_type, json_format = _JSON_TYPES.get(prop.datatype or "", ("string", None))
    schema: dict[str, Any] = {"type": json_type}
    if json_format:
        schema["format"] = json_format
    if prop.min_length is not None:
        schema["minLength"] = prop.min_length
    if prop.max_length is not None:
        schema["maxLength"] = prop.max_length
    if prop.pattern:
        schema["pattern"] = prop.pattern
    if prop.min_inclusive is not None:
        schema["minimum"] = _number(prop.min_inclusive)
    if prop.max_inclusive is not None:
        schema["maximum"] = _number(prop.max_inclusive)
    return schema


def _property_schema(prop: PropertyConstraints) -> dict[str, Any]:
    """The full schema for one property, including array wrapping and annotations."""
    inner = _value_schema(prop)

    if prop.is_multi_valued:
        schema: dict[str, Any] = {"type": "array", "items": inner, "uniqueItems": True}
        # A sh:minCount above 1 constrains how many values there must be, which for an array is
        # minItems. Required-ness itself is expressed in the schema's `required` list.
        if prop.min_count and prop.min_count > 1:
            schema["minItems"] = prop.min_count
        elif prop.min_count:
            schema["minItems"] = 1
        if prop.max_count is not None:
            schema["maxItems"] = prop.max_count
    else:
        schema = inner

    schema["title"] = _title(prop)
    if prop.description:
        schema["description"] = prop.description
    if prop.default is not None:
        schema["default"] = prop.default
    return schema


def _title(prop: PropertyConstraints) -> str:
    """The human-readable control label: `rdfs:label` if the shape gives one, else derived."""
    return prop.label or _humanise(prop.name)


def _humanise(name: str) -> str:
    """``noodleFirmness`` -> ``Noodle firmness``. Only used when a shape gives no rdfs:label."""
    out: list[str] = []
    for index, char in enumerate(name):
        if char.isupper() and index:
            out.append(" ")
            out.append(char.lower())
        else:
            out.append(char)
    text = "".join(out)
    return text[:1].upper() + text[1:]


def _control_options(prop: PropertyConstraints) -> dict[str, Any]:
    """Rendering hints derived from the constraints, never from the field's name."""
    options: dict[str, Any] = {}

    if prop.is_enumerated and not prop.is_multi_valued:
        if len(prop.options) <= _RADIO_MAX_OPTIONS:
            options["format"] = "radio"
    elif prop.datatype == str(XSD.string) and (prop.max_length or 0) >= _MULTILINE_MIN_LENGTH:
        options["multi"] = True
    elif (
        prop.datatype == str(XSD.integer)
        and prop.min_inclusive is not None
        and prop.max_inclusive is not None
        and prop.max_inclusive - prop.min_inclusive <= _SLIDER_MAX_SPAN
    ):
        options["slider"] = True

    if prop.message:
        # Surfaced by the client as the field's hint, so the SHACL message is what the user
        # reads both before and after a failed submission.
        options["hint"] = prop.message
    return options


def _control(prop: PropertyConstraints) -> dict[str, Any]:
    control: dict[str, Any] = {
        "type": "Control",
        "scope": f"#/properties/{prop.name}",
        "label": _title(prop),
    }
    options = _control_options(prop)
    if options:
        control["options"] = options
    return control


def _uischema(properties: tuple[PropertyConstraints, ...]) -> dict[str, Any]:
    """Lay the controls out as one ``Group`` per ``sh:PropertyGroup``.

    SHACL already has a native notion of form grouping, so the layout is modelled data rather
    than a convention invented here. Properties with no ``sh:group`` fall through to a trailing
    ungrouped section instead of being dropped.
    """
    buckets: dict[str, list[dict[str, Any]]] = {}
    order: dict[str, tuple[Decimal, str]] = {}

    for prop in properties:
        key = prop.group.iri if prop.group else _UNGROUPED
        label = prop.group.label if prop.group else "Other"
        rank = prop.group.order if prop.group else Decimal(9999)
        buckets.setdefault(key, []).append(_control(prop))
        order.setdefault(key, (rank, label))

    elements = [
        {"type": "Group", "label": order[key][1], "elements": controls}
        for key, controls in sorted(buckets.items(), key=lambda item: order[item[0]])
    ]
    return {"type": "VerticalLayout", "elements": elements}


def _context_entry(prop: PropertyConstraints) -> dict[str, Any]:
    """The JSON-LD term definition that lifts this field back into RDF."""
    entry: dict[str, Any] = {"@id": prop.path}

    if prop.is_enumerated or prop.node_kind == _SH_IRI:
        # `@type: @vocab` is what lets the wire format stay a plain token ("veganMiso") while
        # the graph gets a real IRI (food:veganMiso) that sh:in and the SPARQL rules can match.
        entry["@type"] = "@vocab"
    elif prop.datatype:
        entry["@type"] = prop.datatype

    if prop.is_multi_valued:
        entry["@container"] = "@set"
    return entry



def build_form(
    properties: tuple[PropertyConstraints, ...],
    *,
    base_context: dict[str, Any],
    title: str,
    description: str | None = None,
) -> FormDefinition:
    """Build the JSON Schema, UI schema and JSON-LD context for one dish."""
    schema_properties: dict[str, Any] = {}
    required: list[str] = []
    key_by_path: dict[str, str] = {}
    token_by_iri: dict[str, str] = {}
    surcharges: dict[str, dict[str, Decimal]] = {}
    context: dict[str, Any] = dict(base_context)

    for prop in properties:
        schema_properties[prop.name] = _property_schema(prop)
        if prop.is_required:
            required.append(prop.name)
        key_by_path[prop.path] = prop.name
        context[prop.name] = _context_entry(prop)
        if prop.options:
            surcharges[prop.name] = {option.token: option.surcharge for option in prop.options}
            for option in prop.options:
                token_by_iri[option.iri] = option.token

    schema: dict[str, Any] = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "title": title,
        "properties": schema_properties,
        # Mirrors `sh:closed true` on the shape: an unknown key is a client bug, and saying so
        # in the schema means the browser catches it before the round trip.
        "additionalProperties": False,
    }
    if description:
        schema["description"] = description
    if required:
        schema["required"] = sorted(required)

    return FormDefinition(
        schema=schema,
        uischema=_uischema(properties),
        context=context,
        key_by_path=key_by_path,
        token_by_iri=token_by_iri,
        surcharges=surcharges,
    )
