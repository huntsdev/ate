from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from sentinelforge.core.database import Base


def test_domain_migration_renders_postgresql_sql(settings):
    output = StringIO()
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"), output_buffer=output)
    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()
    assert "CREATE TABLE alembic_version" in sql
    assert "0001_empty_baseline" in sql
    assert sql.count("CREATE TABLE") == 9
    assert "CREATE EXTENSION" not in sql
    assert set(Base.metadata.tables) == {
        "users",
        "cases",
        "alerts",
        "case_alerts",
        "case_notes",
        "evidence",
        "case_events",
        "case_number_counters",
    }
    assert "cases_require_audit" in sql
    assert "case_events_immutable" in sql
    assert ScriptDirectory.from_config(config).get_heads() == ["0002_domain_persistence"]
