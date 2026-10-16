"""Product Comparison Routes (Live Web & Database).

Provides endpoints for head-to-head comparison of any audio products
using DuckDuckGo live search, specs synthesis, and review pros/cons.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.web_search import compare_products_web

router = APIRouter(prefix="/api/compare", tags=["compare"])


class WebCompareRequest(BaseModel):
    product_a: str = Field(..., min_length=2, max_length=150)
    product_b: str = Field(..., min_length=2, max_length=150)


@router.post("/web")
def compare_web(request: WebCompareRequest) -> dict[str, Any]:
    """Compare any two products side-by-side using live DuckDuckGo web data.

    Returns side-by-side specs, prices in INR across Indian merchants,
    review pros/cons, aspect scores, and category winners.
    """
    return compare_products_web(request.product_a, request.product_b)
