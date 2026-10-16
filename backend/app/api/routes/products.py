"""Product ranking and detail routes (PRD §14.2, §16.4)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import asc, desc, func, nulls_last
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.product import Product
from app.models.review import Review, ReviewStatus
from app.schemas.product import ProductDetailResponse, ProductResponse
from app.schemas.review import ReviewResponse

router = APIRouter(prefix="/api/products", tags=["products"])

SortBy = Literal["corrected_score", "star_average", "review_count", "uncertainty", "rank_position"]
SortOrder = Literal["asc", "desc"]


@router.get("", response_model=list[ProductResponse])
def list_products(
    response: Response,
    sort_by: SortBy = "corrected_score",
    order: SortOrder = "desc",
    category: str | None = Query(default=None, description="Filter by product category ('earbuds', 'headphones', or 'all')"),
    min_price: float | None = Query(default=None, ge=0, description="Minimum price in INR"),
    max_price: float | None = Query(default=None, ge=0, description="Maximum price in INR"),
    search: str | None = Query(default=None, description="Search product title or ASIN"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[Product]:
    """Paginated ranking of scored products.

    Product shells without a completed review are excluded. Ties break on ASIN
    so pagination is stable. ``X-Total-Count`` carries the unpaginated total.
    """
    column = getattr(Product, sort_by)
    direction: Any = desc(column) if order == "desc" else asc(column)
    query = db.query(Product).filter(Product.corrected_score.is_not(None))
    if category and category.lower() != "all":
        query = query.filter(func.lower(Product.product_category) == category.lower())
    if min_price is not None:
        query = query.filter(Product.price_inr >= min_price)
    if max_price is not None:
        query = query.filter(Product.price_inr <= max_price)
    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        query = query.filter(
            func.lower(Product.title).like(term) | func.lower(Product.asin).like(term)
        )

    response.headers["X-Total-Count"] = str(query.count())
    return (
        query.order_by(nulls_last(direction), asc(Product.asin)).offset(offset).limit(limit).all()
    )


@router.get("/{asin}", response_model=ProductDetailResponse)
def get_product(
    asin: str,
    reviews_limit: int = Query(default=20, ge=1, le=100),
    reviews_offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> ProductDetailResponse:
    """Product aggregate plus a newest-first page of its completed reviews."""
    product = db.get(Product, asin)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    base = db.query(Review).filter(
        Review.product_asin == asin, Review.status == ReviewStatus.DONE.value
    )
    total = base.with_entities(func.count(Review.id)).scalar() or 0
    reviews = (
        base.order_by(desc(Review.created_at), desc(Review.id))
        .offset(reviews_offset)
        .limit(reviews_limit)
        .all()
    )
    return ProductDetailResponse.model_validate(
        {
            **ProductResponse.model_validate(product).model_dump(),
            "eb_shrinkage_factor": product.eb_shrinkage_factor,
            "aspect_summary": product.aspect_summary,
            "last_aggregated_at": product.last_aggregated_at,
            "reviews": [ReviewResponse.model_validate(r) for r in reviews],
            "reviews_total": total,
            "reviews_limit": reviews_limit,
            "reviews_offset": reviews_offset,
            "reviews_has_more": reviews_offset + len(reviews) < total,
        }
    )
