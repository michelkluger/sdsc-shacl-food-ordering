"""SHACL-driven food ordering API."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("food-api")
except PackageNotFoundError:  # pragma: no cover - only hit in a source tree with no install
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
