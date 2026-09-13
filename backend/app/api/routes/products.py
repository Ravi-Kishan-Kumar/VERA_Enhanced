"""Product-ranking and product-detail routes."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import asc, desc, nullslast
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db
from app.models.product import Product
from app.schemas.product import ProductDetailResponse, ProductResponse

router = APIRouter(prefix="/api/products", tags=["products"])

SortBy = Literal["corrected_score", "review_count", "uncertainty"]
SortOrder = Literal["asc", "desc"]


@router.get("", response_model=list[ProductResponse])
def list_products(
    sort_by: SortBy = "corrected_score",
    order: SortOrder = "desc",
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[Product]:
    """Return a stable, paginated product ranking."""
    column = getattr(Product, sort_by)
    direction: Any = desc(column) if order == "desc" else asc(column)
    return (
        db.query(Product)
        .order_by(nullslast(direction), asc(Product.asin))
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get("/{asin}", response_model=ProductDetailResponse)
def get_product(asin: str, db: Session = Depends(get_db)) -> Product:
    """Return a product with every associated review."""
    product = (
        db.query(Product)
        .options(selectinload(Product.reviews))
        .filter(Product.asin == asin)
        .first()
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product
