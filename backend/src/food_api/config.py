"""Application settings.

Everything is overridable by environment variable so the same image runs locally, in Compose
and in CI without a code change. The one setting that genuinely differs between those is
``FOOD_API_MEILI_URL`` (``localhost`` vs the Compose service name).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_PACKAGE_ROOT = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """Runtime configuration, read from the environment with a ``FOOD_API_`` prefix."""

    model_config = SettingsConfigDict(
        env_prefix="FOOD_API_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "SHACL-driven food ordering API"
    debug: bool = False

    data_dir: Path = Field(
        default=_PACKAGE_ROOT / "data",
        description="Root of the JSON-LD / SHACL corpus. Dishes are discovered underneath it.",
    )

    base_iri: str = Field(
        default="https://sdsc.example/ns/food#",
        description="Namespace the vocabulary and every generated @context are rooted at.",
    )

    meili_url: str = "http://localhost:7700"
    meili_master_key: str | None = None
    meili_index: str = "dishes"
    meili_timeout_seconds: int = 5

    # Meilisearch is an enhancement, not a dependency: when it is unreachable the API keeps
    # serving forms and validating orders, and only /api/search degrades. Set this to True to
    # make an unreachable Meilisearch a hard startup failure instead.
    require_search: bool = False

    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:4173"],
        description=(
            "Origins allowed to call the API from a browser (the Vite dev and preview servers)."
        ),
    )

    @property
    def vocab_path(self) -> Path:
        return self.data_dir / "vocab" / "food.ttl"

    @property
    def common_shapes_path(self) -> Path:
        return self.data_dir / "shapes" / "common.ttl"

    @property
    def base_context_path(self) -> Path:
        return self.data_dir / "context" / "base.jsonld"

    @property
    def dishes_dir(self) -> Path:
        return self.data_dir / "dishes"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings, parsed once."""
    return Settings()
