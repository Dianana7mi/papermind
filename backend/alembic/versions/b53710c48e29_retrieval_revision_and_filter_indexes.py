"""Cross-replica lexical cache revisions and indexed experiment JSON conditions."""
from alembic import op
import sqlalchemy as sa

revision = "b53710c48e29"
down_revision = "63fa391b4bb1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("libraries", sa.Column("retrieval_revision", sa.Integer(), nullable=False, server_default="0"))
    for field in ("average_bits", "bit_width", "method_name", "model_architecture"):
        value = sa.column("record", sa.JSON)[field].as_string()
        value = sa.cast(value, sa.Numeric(38, 16)) if field in ("average_bits", "bit_width") else sa.func.lower(sa.func.trim(value))
        op.create_index(f"ix_experiment_json_{field}", "experiments", ["owner_id", "library_id", value])


def downgrade():
    for field in ("average_bits", "bit_width", "method_name", "model_architecture"):
        op.drop_index(f"ix_experiment_json_{field}", table_name="experiments")
    op.drop_column("libraries", "retrieval_revision")
