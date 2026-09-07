"""RDF namespaces used across the project."""

from __future__ import annotations

from rdflib import Namespace

#: The project vocabulary. Kept in one place so the IRI appears exactly once in Python.
FOOD = Namespace("https://sdsc.example/ns/food#")

#: schema.org, used for the catalogue half of the model (name, description, image).
SCHEMA = Namespace("https://schema.org/")

#: Every order is minted under this prefix. Orders are not persisted, so the IRI only needs to
#: be stable within a single validation run.
ORDER_BASE = "urn:food:order:"


def localname(iri: str) -> str:
    """The last segment of an IRI: ``food:veganMiso`` -> ``veganMiso``.

    Used wherever an IRI has to become something a person or a JSON document reads - an option
    token, a constraint name, a fallback field name. Lives here rather than in either caller
    because the shape reader and the report reader both need it, and two copies of "how we
    shorten an IRI" is exactly the kind of thing that drifts apart unnoticed.

    Both separators are tried in turn, so a hash namespace and a slash namespace shorten alike
    and ``#`` wins when an IRI has both - which is what every vocabulary here relies on. A
    separator with nothing after it is skipped rather than honoured, and an IRI that yields no
    tail at all comes back whole: an empty label renders as a blank control or a nameless
    constraint, which is worse than an ugly one.
    """
    for separator in ("#", "/"):
        if separator in iri:
            tail = iri.rpartition(separator)[2]
            if tail:
                return tail
    return iri
