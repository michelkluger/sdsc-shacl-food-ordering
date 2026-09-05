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
