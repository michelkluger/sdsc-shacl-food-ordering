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


def _localname(iri: str) -> str:
    for sep in ("#", "/"):
        if sep in iri:
            tail = iri.rpartition(sep)[2]
            if tail:
                return tail
    return iri


def _compact(node: Node | None, form: FormDefinition) -> Any:
    """Render a report value the way the client sent it: a token, not an IRI."""
    if node is None:
        return None
    if isinstance(node, URIRef):
        iri = str(node)
        return form.token_by_iri.get(iri, _localname(iri))
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


def _messages(report: Graph, result: Node) -> list[str]:
    return [str(message) for message in report.objects(result, SH.resultMessage)]


def collect_violations(
    report: Graph,
    form: FormDefinition,
    payload: dict[str, Any],
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
            candidate = _localname(path)
            field = candidate if candidate in payload else None

        value = _compact(value_node, form)
        messages = _messages(report, result)
        constraint = _localname(str(constraint_node)) if constraint_node is not None else "Unknown"

        violations.append(
            Violation(
                pointer=_pointer_for(field, value, payload),
                field=field,
                path=path,
                constraint=constraint,
                severity=SEVERITY_LABELS.get(str(severity_node), "violation"),
                message=_message_for(constraint, messages, field, path),
                value=value,
            )
        )

    violations.sort(key=lambda violation: (violation.pointer, violation.constraint))
    return violations


def _message_for(
    constraint: str,
    messages: list[str],
    field: str | None,
    path: str | None,
) -> str:
    """Choose the message a user should read for one violation.

    ``sh:closed`` is handled here rather than with an ``sh:message`` on the node shape: SHACL
    applies a node shape's message to *every* constraint it carries, so declaring one there
    would append "unknown field" to unrelated violations. It is also the one constraint whose
    generated message names the internal order IRI, which no client should ever see.
    """
    if constraint == "ClosedConstraintComponent":
        name = field or (_localname(path) if path else "a field")
        return f"{name!r} is not a field of this dish's form."
    if messages:
        return " ".join(messages)

    # Every shape in this project sets sh:message; this keeps a future dish that forgets from
    # returning an empty string.
    target = f"{field!r}" if field else "the order"
    readable = constraint.removesuffix("ConstraintComponent")
    return f"{target} does not satisfy the {readable} constraint."
