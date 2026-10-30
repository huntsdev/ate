from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import AnyHttpUrl, Field, RedisDsn, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class ConfigurationError(ValueError):
    """A safe configuration error that never includes setting values."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ATE_", extra="ignore", hide_input_in_errors=True)

    postgres_password: SecretStr = Field(min_length=12)
    postgres_user: str = Field(default="ate", min_length=1)
    postgres_db: str = Field(default="ate", min_length=1)
    postgres_host: str = Field(default="postgres", min_length=1)
    postgres_port: int = Field(default=5432, ge=1, le=65535)
    redis_url: RedisDsn = RedisDsn("redis://redis:6379/0")
    readiness_timeout_seconds: float = Field(default=2, ge=0.1, le=10)
    ollama_url: AnyHttpUrl = AnyHttpUrl("http://host.docker.internal:11434")
    ollama_model: str = Field(default="qwen3:8b", min_length=1, max_length=200)
    elastic_url: AnyHttpUrl | None = None
    trusted_hosts: list[str] = ["127.0.0.1", "localhost"]
    browser_origins: list[str] = [
        f"http://{host}:{port}"
        for host in ("127.0.0.1", "localhost")
        for port in (8000, 8080, 5173, 4173)
    ]

    @field_validator("trusted_hosts")
    @classmethod
    def loopback_hosts(cls, values: list[str]) -> list[str]:
        if not values or any(value not in {"127.0.0.1", "localhost"} for value in values):
            raise ValueError("Only loopback development hosts are supported")
        return values

    @field_validator("browser_origins")
    @classmethod
    def loopback_origins(cls, values: list[str]) -> list[str]:
        for value in values:
            parsed = urlsplit(value)
            if (
                parsed.scheme not in {"http", "https"}
                or parsed.hostname not in {"127.0.0.1", "localhost"}
                or parsed.username
                or parsed.password
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("Browser origins must be loopback HTTP(S) origins without paths")
            if parsed.port is not None and not 1 <= parsed.port <= 65535:
                raise ValueError("Invalid browser origin port")
        if not values:
            raise ValueError("At least one browser origin is required")
        return values

    @field_validator("elastic_url", mode="before")
    @classmethod
    def optional_elastic_url(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("postgres_host", "postgres_user", "postgres_db", "ollama_model")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value

    @property
    def database_url(self) -> URL:
        return URL.create(
            "postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        fields = sorted({str(error["loc"][0]) for error in exc.errors()})
        raise ConfigurationError(f"Invalid configuration fields: {', '.join(fields)}") from None
