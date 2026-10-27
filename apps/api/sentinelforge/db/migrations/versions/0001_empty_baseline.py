"""Empty Phase 0 baseline: only Alembic's revision tracking table is created."""

revision = "0001_empty_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
