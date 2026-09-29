"""
Settings, read from the environment.

Nothing here has a hardcoded host or origin. The previous backend shipped
``allow_origins=["*"]`` with no authentication, on a container using the host
network alongside an unauthenticated rosbridge — so anyone with network reach
to the machine could drive the robot and delete its maps. That is an explicit
choice now, and production refuses to start if it is left wide open.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AMR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Literal["development", "production"] = "development"

    db_path: Path = Path("./data/amr.db")
    maps_dir: Path = Path("./data/maps")
    # The maps directory as the ROS container sees it. In docker-compose both
    # mount the same volume, but at paths that need not match.
    ros_maps_path: str = "/maps"

    host: str = "0.0.0.0"  # noqa: S104 — container-local; published ports are set in compose.
    port: int = 3002

    # NoDecode turns off pydantic-settings' JSON decoding for this field.
    # Without it, a .env line like `AMR_CORS_ORIGINS=http://a,http://b` is fed
    # to json.loads before any validator runs, and startup dies on a config
    # file that reads perfectly well to a human.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3100"]
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accept a comma-separated string, which is what .env files carry."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    def validate_for_runtime(self) -> None:
        """
        Fail loudly rather than serving an unsafe configuration.

        Called at startup. A wildcard origin in production is the exact defect
        the previous backend shipped, so it is refused rather than warned about.
        """
        if self.is_production and "*" in self.cors_origins:
            raise ValueError(
                "AMR_CORS_ORIGINS must name explicit origins in production; '*' is refused."
            )
        if not self.cors_origins:
            raise ValueError(
                "AMR_CORS_ORIGINS is empty; no browser would be able to call this API."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
