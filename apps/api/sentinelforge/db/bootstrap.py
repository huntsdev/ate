"""Run migrations as owner, then provision the restricted application login."""

import psycopg
from alembic import command
from alembic.config import Config
from psycopg import sql
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from sentinelforge.core.config import Settings, get_settings
from sentinelforge.domains.identity import LOCAL_ANALYST_HANDLE, LOCAL_ANALYST_ID


class RuntimeRoleSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ATE_", extra="ignore", hide_input_in_errors=True)
    postgres_app_user: str = Field(
        default="ate_app", min_length=1, max_length=63, pattern=r"^[a-z][a-z0-9_]*$"
    )
    postgres_app_password: SecretStr = Field(min_length=12)


def provision_runtime_role(settings: Settings, role: RuntimeRoleSettings) -> None:
    if role.postgres_app_user == settings.postgres_user:
        raise ValueError("Application and migration users must differ")
    if (
        role.postgres_app_password.get_secret_value()
        == settings.postgres_password.get_secret_value()
    ):
        raise ValueError("Application and migration passwords must differ")
    url = settings.database_url.set(drivername="postgresql")
    with psycopg.connect(url.render_as_string(hide_password=False)) as connection:
        existing = connection.execute(
            "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls "
            "FROM pg_roles WHERE rolname = %s",
            (role.postgres_app_user,),
        ).fetchone()
        if existing and any(existing):
            raise ValueError("Refusing to reuse a privileged application role")
        if connection.execute(
            "SELECT 1 FROM pg_auth_members WHERE member = "
            "(SELECT oid FROM pg_roles WHERE rolname = %s)",
            (role.postgres_app_user,),
        ).fetchone():
            raise ValueError("Application role must not inherit other roles")
        identifier = sql.Identifier(role.postgres_app_user)
        if existing is None:
            connection.execute(
                sql.SQL(
                    "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                    "NOREPLICATION NOBYPASSRLS"
                ).format(identifier)
            )
        connection.execute(
            sql.SQL("ALTER ROLE {} LOGIN NOINHERIT PASSWORD {}").format(
                identifier, sql.Literal(role.postgres_app_password.get_secret_value())
            )
        )
        connection.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(settings.postgres_db), identifier
            )
        )
        connection.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(identifier))
        connection.execute(sql.SQL("REVOKE CREATE ON SCHEMA public FROM {}").format(identifier))
        connection.execute(
            sql.SQL("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {}").format(identifier)
        )
        connection.execute(
            sql.SQL(
                "GRANT SELECT, INSERT, UPDATE ON users, cases, "
                "case_notes, evidence, case_number_counters TO {}"
            ).format(identifier)
        )
        connection.execute(
            sql.SQL("GRANT SELECT, INSERT ON alerts, case_alerts TO {}").format(identifier)
        )
        connection.execute(sql.SQL("GRANT DELETE ON case_alerts TO {}").format(identifier))
        connection.execute(sql.SQL("GRANT SELECT, INSERT ON case_events TO {}").format(identifier))
        connection.execute(sql.SQL("GRANT SELECT ON alembic_version TO {}").format(identifier))


def ensure_local_analyst(settings: Settings) -> None:
    url = settings.database_url.set(drivername="postgresql")
    with psycopg.connect(url.render_as_string(hide_password=False)) as connection:
        connection.execute(
            "INSERT INTO users (id, handle, kind, auth_source) VALUES (%s, %s, 'human', 'local') "
            "ON CONFLICT (id) DO NOTHING",
            (LOCAL_ANALYST_ID, LOCAL_ANALYST_HANDLE),
        )
        row = connection.execute(
            "SELECT handle, kind, auth_source, is_active FROM users WHERE id = %s",
            (LOCAL_ANALYST_ID,),
        ).fetchone()
        if row != (LOCAL_ANALYST_HANDLE, "human", "local", True):
            raise ValueError("The reserved local analyst identity is unavailable")


def main() -> None:
    try:
        settings = get_settings()
        role = RuntimeRoleSettings()
        command.upgrade(Config("alembic.ini"), "head")
        provision_runtime_role(settings, role)
        ensure_local_analyst(settings)
        print("Migrations and restricted application role: ready.")
    except Exception as exc:
        # Database/validation errors can contain connection strings or passwords.
        raise SystemExit(f"Database bootstrap failed: {type(exc).__name__}") from None


if __name__ == "__main__":
    main()
