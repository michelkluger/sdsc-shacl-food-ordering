"""Turn a SHACL validation report graph into errors a form can display.

pySHACL hands back a ``sh:ValidationReport`` graph. A browser needs a list of violations keyed
by JSON pointer, because that is how JSON Forms attaches an error to a control. This module is
the bridge, and it is the reason ``FormDefinition`` keeps ``key_by_path``: the same map that
decided a property's JSON key when the form was generated decides it again in reverse here, so
a field's name in the form and in its error can never disagree.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import SH
from rdflib.term import Node

from food_api.namespaces import localname
from food_api.shacl.introspect import DEFAULT_LANGUAGE, select_literal
from food_api.shacl.jsonforms import FormDefinition

SEVERITY_LABELS: dict[str, str] = {
    str(SH.Violation): "violation",
    str(SH.Warning): "warning",
    str(SH.Info): "info",
}


@dataclass(frozen=True, slots=True)
class Violation:
    """One constraint failure, addressed at the field that caused it."""

    pointer: str
    field: str | None
    path: str | None
    constraint: str
    severity: str
    message: str
    value: Any = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "pointer": self.pointer,
            "field": self.field,
            "path": self.path,
            "constraint": self.constraint,
            "severity": self.severity,
            "message": self.message,
            "value": self.value,
        }


def _compact(node: Node | None, form: FormDefinition) -> Any:
    """Render a report value the way the client sent it: a token, not an IRI."""
    if node is None:
        return None
    if isinstance(node, URIRef):
        iri = str(node)
        return form.token_by_iri.get(iri, localname(iri))
    if isinstance(node, Literal):
        return node.toPython()
    return str(node)


def _pointer_for(field: str | None, value: Any, payload: dict[str, Any]) -> str:
    """Build the JSON pointer for a violation.

    For an array-valued field the pointer addresses the offending element, so a client can put
    the message on the exact chip the user picked rather than on the whole control. Falling back
    to the field, and then to the document root, keeps every violation addressable even when the
    report cannot be attributed precisely.
    """
    if field is None:
        return ""
    submitted = payload.get(field)
    if isinstance(submitted, list) and value is not None:
        try:
            return f"/{field}/{submitted.index(value)}"
        except ValueError:
            return f"/{field}"
    return f"/{field}"


def _messages(
    report: Graph,
    result: Node,
    language: str,
    shapes: Graph | None = None,
) -> list[str]:
    """Pick the report messages for ``language``.

    A shape may declare ``sh:message`` several times with different language tags. For core
    constraints pySHACL copies each one into ``sh:resultMessage`` with its tag intact, so the
    right one can simply be selected here - no translation table in Python, and no second place
    for the wording to live.

    **For ``sh:sparql`` constraints it does not.** pySHACL runs template substitution on those
    messages and rebuilds them as plain literals, dropping the tag, so every language arrives
    indistinguishable and a naive reader concatenates all five. When the report names the
    constraint via ``sh:sourceConstraint`` we therefore go back to the shapes graph and select
    the tagged literal from the source of truth instead.
    """
    if shapes is not None:
        source = report.value(result, SH.sourceConstraint)
        if source is not None:
            from_shape = select_literal(shapes, source, SH.message, language)
            if from_shape:
                return [from_shape]

    literals = [
        message
        for message in report.objects(result, SH.resultMessage)
        if isinstance(message, Literal)
    ]
    if not literals:
        return []

    wanted = language.lower()
    base = wanted.partition("-")[0]

    for predicate in (
        lambda tag: tag == wanted,
        lambda tag: tag.partition("-")[0] == base,
        lambda tag: tag.partition("-")[0] == DEFAULT_LANGUAGE,
        lambda tag: not tag,
    ):
        matching = [str(lit) for lit in literals if predicate((lit.language or "").lower())]
        if matching:
            # More than one match at the untagged step means the tags were lost somewhere.
            # Returning all of them would concatenate every language into one message, so take
            # the first rather than producing something unreadable.
            return matching[:1] if len(matching) > 1 else matching

    return [str(literals[0])]


def collect_violations(
    report: Graph,
    form: FormDefinition,
    payload: dict[str, Any],
    *,
    language: str = DEFAULT_LANGUAGE,
    shapes: Graph | None = None,
) -> list[Violation]:
    """Read every ``sh:ValidationResult`` out of ``report``, newest-shape-agnostic.

    Results are sorted by pointer so a given invalid payload always produces the same error
    list. Report graphs are unordered, and an unstable order would make golden tests flap and
    make the UI reshuffle its messages between identical submissions.
    """
    violations: list[Violation] = []

    for result in report.subjects(SH.resultSeverity, None):
        severity_node = report.value(result, SH.resultSeverity)
        constraint_node = report.value(result, SH.sourceConstraintComponent)
        path_node = report.value(result, SH.resultPath)
        value_node = report.value(result, SH.value)

        path = str(path_node) if path_node is not None else None
        field = form.key_by_path.get(path) if path else None
        if field is None and path:
            # `sh:closed` reports the *offending* predicate, which by definition is not one of
            # the shape's known paths. Recover the client's key from the local name when the
            # payload actually carries it, so "unknown field" lands on that field.
            candidate = localname(path)
            field = candidate if candidate in payload else None

        value = _compact(value_node, form)
        messages = _messages(report, result, language, shapes)
        constraint = localname(str(constraint_node)) if constraint_node is not None else "Unknown"

        violations.append(
            Violation(
                pointer=_pointer_for(field, value, payload),
                field=field,
                path=path,
                constraint=constraint,
                severity=SEVERITY_LABELS.get(str(severity_node), "violation"),
                message=_message_for(constraint, messages, field, path, language),
                value=value,
            )
        )

    violations.sort(key=lambda violation: (violation.pointer, violation.constraint))
    return violations


#: The only user-facing string in the backend that is not declared by a shape. See below.
CLOSED_MESSAGES: dict[str, str] = {
    "en": "'{field}' is not a field of this dish's form.",
    "de": "'{field}' ist kein Feld dieses Formulars.",
    "fr": "'{field}' n'est pas un champ de ce formulaire.",
    "it": "'{field}' non e un campo di questo modulo.",
    "rm": "'{field}' n'e betg in champ da quest formular.",
}


def _message_for(
    constraint: str,
    messages: list[str],
    field: str | None,
    path: str | None,
    language: str = DEFAULT_LANGUAGE,
) -> str:
    """Choose the message a user should read for one violation.

    ``sh:closed`` is handled here rather than with an ``sh:message`` on the node shape: SHACL
    applies a node shape's message to *every* constraint it carries, so declaring one there
    would append "unknown field" to unrelated violations. It is also the one constraint whose
    generated message names the internal order IRI, which no client should ever see.
    """
    if constraint == "ClosedConstraintComponent":
        name = field or (localname(path) if path else "?")
        # The one message in the system with no shape behind it: pySHACL generates it, and its
        # generated text names the internal order IRI. Because there is no sh:message to
        # translate, the wording lives here - the single exception to "messages come from the
        # shapes", and worth keeping to exactly one.
        template = CLOSED_MESSAGES.get(language, CLOSED_MESSAGES[DEFAULT_LANGUAGE])
        return template.format(field=name)
    if messages:
        return " ".join(messages)

    # Every shape in this project sets sh:message; this keeps a future dish that forgets from
    # returning an empty string.
    target = f"{field!r}" if field else "the order"
    readable = constraint.removesuffix("ConstraintComponent")
    return f"{target} does not satisfy the {readable} constraint."
