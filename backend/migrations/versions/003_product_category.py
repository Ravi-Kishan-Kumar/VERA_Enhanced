"""Add product_category and price_inr columns.

Revision ID: 003_product_category
Revises: 002_jobs_outbox
Create Date: 2026-10-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "003_product_category"
down_revision = "002_jobs_outbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add product_category and price_inr to products
    op.add_column(
        "products",
        sa.Column(
            "product_category",
            sa.String(length=20),
            nullable=False,
            server_default="earbuds",
        ),
    )
    op.add_column(
        "products",
        sa.Column("price_inr", sa.Float(), nullable=True),
    )
    op.create_index("idx_products_category", "products", ["product_category"])

    # Add product_category to reviews
    op.add_column(
        "reviews",
        sa.Column(
            "product_category",
            sa.String(length=20),
            nullable=False,
            server_default="earbuds",
        ),
    )
    op.create_index("idx_reviews_category", "reviews", ["product_category"])


def downgrade() -> None:
    op.drop_index("idx_reviews_category", table_name="reviews")
    op.drop_column("reviews", "product_category")
    op.drop_index("idx_products_category", table_name="products")
    op.drop_column("products", "price_inr")
    op.drop_column("products", "product_category")
