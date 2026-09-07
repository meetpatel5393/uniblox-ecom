from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.admin import AdminReportResponse
from app.schemas.coupon import (
    CouponListResponse,
    CouponResponse,
    DeleteCouponResponse,
    GenerateCouponsRequest,
    GenerateCouponsResponse,
    MilestoneStatusResponse,
)
from app.services import admin as admin_service
from app.services import coupon as coupon_service

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post(
    "/coupons/generate",
    response_model=GenerateCouponsResponse,
    summary="[Admin] Generate milestone coupon pool",
    description=(
        "Creates a single discount coupon code for a given `milestone_n` with a set number of allowed uses.  \n\n"
        "**`milestone_n`** — the nth-order milestone this coupon belongs to (e.g. `5` for every 5th order).  \n"
        "**`max_uses`** — how many times this one code can be redeemed (1–500).  \n\n"
        "Can be called at any time — no orders need to exist first. "
        "Customers enter the code at checkout; each redemption decrements the remaining uses. "
        "If uses run out, checkout continues without a discount.  \n\n"
        "The code is unique (e.g. `MILE5-AB12CD`), with a configurable "
        "discount % and minimum order threshold from environment variables."
    ),
    responses={
        201: {"description": "Coupons created. Includes pool_size remaining for this milestone."},
        422: {"description": "count < 1 or count > 500, or milestone_n < 1."},
    },
    status_code=201,
)
def generate_coupons(payload: GenerateCouponsRequest, db: Session = Depends(get_db)):
    return coupon_service.generate_milestone_coupons(db, payload)


@router.get(
    "/coupons/milestones",
    response_model=MilestoneStatusResponse,
    summary="[Admin] Get order milestone progress & eligibility",
    description=(
        "Returns current order milestone progress: total placed orders, reached milestones, "
        "coupons already issued, and milestones ready to be generated."
    ),
    responses={
        200: {"description": "Current order milestone progress."},
    },
)
def get_milestone_status(interval_n: int | None = None, db: Session = Depends(get_db)):
    return coupon_service.get_milestone_status(db, interval_n)


@router.get(
    "/coupons",
    response_model=CouponListResponse,
    summary="[Admin] List coupons (paginated)",
    description=(
        "Returns coupons paginated. `uses_remaining = max_uses - redemption_count`. "
        "A coupon with `uses_remaining = 0` cannot be applied at checkout."
    ),
    responses={
        200: {"description": "Paginated coupon list."},
    },
)
def list_coupons(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    return coupon_service.list_coupons_paginated(db, page, page_size)


@router.delete(
    "/coupons/{code_or_id}",
    response_model=DeleteCouponResponse,
    summary="[Admin] Delete unredeemed coupon",
    description=(
        "Deletes a created coupon ONLY if it has never been used. "
        "If the coupon has already been redeemed by any order, returns 409 Conflict."
    ),
    responses={
        200: {"description": "Coupon deleted successfully."},
        404: {"description": "Coupon not found."},
        409: {"description": "Coupon has already been used and cannot be deleted."},
    },
)
def delete_coupon(code_or_id: str, db: Session = Depends(get_db)):
    return coupon_service.delete_coupon(db, code_or_id)


@router.get(
    "/report",
    response_model=AdminReportResponse,
    summary="[Admin] Sales report",
    description=(
        "Aggregated sales statistics across all placed orders.  \n\n"
        "**Revenue:**  \n"
        "- `gross_revenue_cents` — sum of order gross totals before discounts  \n"
        "- `total_discount_cents` — total discount granted across all orders  \n"
        "- `net_revenue_cents` — sum of order net totals after discounts  \n\n"
        "**Products:**  \n"
        "- `products_sold` — per-product quantity sold and revenue, ordered by qty descending  \n\n"
        "**Coupons:**  \n"
        "- `coupons_generated` — total coupons ever created  \n"
        "- `coupons_available` — coupons with at least one remaining use  \n"
        "- `coupons_redeemed` — number of orders that used a coupon  \n"
        "- `discount_codes_used` — distinct coupon codes that have been redeemed  \n\n"
        "All amounts are in integer cents. "
        "Repeated calls do **not** mutate state."
    ),
    responses={
        200: {"description": "Aggregated sales report."},
    },
)
def get_report(db: Session = Depends(get_db)):
    return admin_service.get_report(db)
