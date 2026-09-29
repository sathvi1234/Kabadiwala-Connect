"""Initial schema."""

from alembic import op

from app.database import Base
import app.models  # noqa: F401

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    Base.metadata.create_all(bind)


def downgrade():
    bind = op.get_bind()
    Base.metadata.drop_all(bind)
