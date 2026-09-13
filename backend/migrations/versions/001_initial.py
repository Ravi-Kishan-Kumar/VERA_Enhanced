"""Create the VERA application schema.

Revision ID: 001_initial
Revises:
Create Date: 2026-09-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create products first because reviews references its ASIN."""
    op.create_table(
        "products",
        sa.Column("asin", sa.String(length=20), primary_key=True),
        sa.Column("title", sa.Text()),
        sa.Column("corrected_score", sa.Float()),
        sa.Column("uncertainty", sa.Float()),
        sa.Column("trust_weighted_score", sa.Float()),
        sa.Column("star_average", sa.Float()),
        sa.Column("eb_shrinkage_factor", sa.Float()),
        sa.Column("review_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("aspect_summary", sa.JSON()),
        sa.Column("rank_position", sa.Integer()),
        sa.Column("previous_rank_position", sa.Integer()),
        sa.Column("last_aggregated_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("idx_products_rank", "products", ["rank_position"])

    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("star_rating", sa.Float(), nullable=False),
        sa.Column("helpful_votes", sa.Integer()),
        sa.Column("verified_purchase", sa.Boolean()),
        sa.Column("product_title", sa.Text()),
        sa.Column(
            "product_asin",
            sa.String(length=20),
            sa.ForeignKey("products.asin", ondelete="SET NULL"),
        ),
        sa.Column("corrected_score", sa.Float()),
        sa.Column("interval_lower", sa.Float()),
        sa.Column("interval_upper", sa.Float()),
        sa.Column("confidence_value", sa.Float()),
        sa.Column("star_text_gap", sa.Float()),
        sa.Column("review_quality", sa.Float()),
        sa.Column("aspects", sa.JSON()),
        sa.Column("flags", sa.JSON()),
        sa.Column("explanation", sa.Text()),
        sa.Column("error_message", sa.Text()),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("star_rating >= 1 AND star_rating <= 5", name="ck_reviews_star_range"),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'done', 'failed')", name="ck_reviews_status"
        ),
    )
    op.create_index("idx_reviews_asin", "reviews", ["product_asin"])
    op.create_index("idx_reviews_status", "reviews", ["status"])

    op.create_table(
        "label_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("review_text_hash", sa.String(length=64), nullable=False),
        sa.Column("labeler", sa.String(length=100), nullable=False),
        sa.Column("experience_score", sa.Float()),
        sa.Column("aspects", sa.JSON()),
        sa.Column("has_irony", sa.Boolean()),
        sa.Column("review_quality", sa.String(length=10)),
        sa.Column("raw_response", sa.JSON()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("idx_label_runs_hash", "label_runs", ["review_text_hash"])

    op.create_table(
        "calibration_checkpoints",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("method", sa.String(length=20), nullable=False, server_default="absolute"),
        sa.Column("q_hat", sa.Float(), nullable=False),
        sa.Column("empirical_coverage", sa.Float(), nullable=False),
        sa.Column("nominal_coverage", sa.Float(), nullable=False),
        sa.Column("calibration_set_size", sa.Integer(), nullable=False),
        sa.Column(
            "fitted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    """Drop in dependency order."""
    op.drop_table("calibration_checkpoints")
    op.drop_index("idx_label_runs_hash", table_name="label_runs")
    op.drop_table("label_runs")
    op.drop_index("idx_reviews_status", table_name="reviews")
    op.drop_index("idx_reviews_asin", table_name="reviews")
    op.drop_table("reviews")
    op.drop_index("idx_products_rank", table_name="products")
    op.drop_table("products")
