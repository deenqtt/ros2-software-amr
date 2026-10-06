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

from pydantic import Field, SecretStr, field_validator
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

    # Sign-in. A session ends after this long without a request; 12 hours is
    # one shift, so nobody is signed out mid-shift and a screen left on
    # overnight is not still signed in at the next one.
    session_idle_minutes: int = Field(default=12 * 60, ge=5)
    # Send the session cookie over HTTPS only. Leave off while the site is
    # served over plain HTTP (the nginx example is), or the browser drops the
    # cookie and every sign-in appears to fail.
    cookie_secure: bool = False
    # Production refuses to start with cookie_secure off: over plain HTTP the
    # session cookie and every password cross the network readable by anyone
    # on it. Set this to true to accept that knowingly — a closed test network,
    # or until a certificate is in place. Never needed once TLS is on.
    allow_insecure_http: bool = False
    # How a robot agent is let in. `required`: only with its own bearer token
    # (minted per robot by an admin: POST /api/robots/{id}/agent-token).
    # `optional`: additionally, a request with no credentials at all is taken
    # to be an unbound agent — for local development only; production refuses
    # to start with it.
    agent_auth: Literal["optional", "required"] = "required"
    audit_retention_days: int = Field(default=365, ge=1)

    # The first super admin on a fresh server. Read only while the database has
    # no accounts at all; the account must replace this password at first
    # sign-in, so what sits in .env stops being a working password the moment
    # someone has used it. Remove both lines once that has happened.
    bootstrap_user: str | None = None
    bootstrap_password: SecretStr | None = None

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
        if self.is_production and self.agent_auth == "optional":
            raise ValueError(
                "AMR_AGENT_AUTH=optional lets anything without credentials act as a robot "
                "agent; it is refused in production. Give each agent a token instead."
            )
        if self.is_production and not self.cookie_secure and not self.allow_insecure_http:
            raise ValueError(
                "AMR_COOKIE_SECURE=false in production: the session cookie and passwords "
                "would cross the network in clear text. Serve the site over HTTPS (see "
                "new_webui/deploy/nginx-tls.conf.example) and set AMR_COOKIE_SECURE=true, "
                "or, to run over plain HTTP anyway (a closed test network), set "
                "AMR_ALLOW_INSECURE_HTTP=true."
            )
        if not self.cors_origins:
            raise ValueError(
                "AMR_CORS_ORIGINS is empty; no browser would be able to call this API."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
