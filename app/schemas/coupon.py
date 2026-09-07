import uuid

from typing import Literal, Optional

from pydantic import BaseModel, Field


class CouponResponse(BaseModel):
    id: uuid.UUID
    code: str
    discount_pct: int
    discount_type: str = "percent"
    discount_amount_cents: Optional[int] = None
    min_order_cents: int
    milestone_n: int
    uses_remaining: int
    max_uses: int = 1
    is_used: bool = False


class MilestoneStatusResponse(BaseModel):
    total_orders: int
    milestone_interval_n: int
    default_discount_pct_x: int
    default_min_order_cents: int
    reached_milestones: list[int]
    generated_milestones: list[int]
    eligible_unissued_milestones: list[int]
    next_milestone: int
    orders_until_next: int


class GenerateCouponsRequest(BaseModel):
    milestone_n: Optional[int] = Field(
        None,
        ge=1,
        description="Specific milestone order count (e.g. 5, 10). If omitted, scans and generates for all reached unissued milestones.",
    )
    milestone_interval_n: Optional[int] = Field(
        None,
        ge=1,
        description="Milestone interval n (defaults to COUPON_EVERY_N_ORDERS = 5)",
    )
    max_uses: int = Field(
        1,
        ge=1,
        le=500,
        description="How many times the coupon code can be redeemed (default 1 = single-use per specification)",
    )
    discount_type: Literal["percent", "fixed"] = Field(
        "percent",
        description="Discount mode: 'percent' for percentage discount, 'fixed' for fixed cash discount",
    )
    discount_pct: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Discount percentage x (1-100) when discount_type is 'percent' (default from config: 10%)",
    )
    discount_amount_cents: Optional[int] = Field(
        None,
        ge=0,
        description="Discount amount in cents when discount_type is 'fixed'",
    )
    min_order_cents: Optional[int] = Field(
        None,
        ge=0,
        description="Minimum order cart value in cents required to redeem this coupon",
    )
    force: bool = Field(
        False,
        description="Allow generating a coupon even if milestone not yet reached or already generated (for manual testing)",
    )


class GenerateCouponsResponse(BaseModel):
    generated: int
    message: str
    coupons: list[CouponResponse]
    pool_size: int
    milestone_status: Optional[MilestoneStatusResponse] = None


class CouponListResponse(BaseModel):
    items: list[CouponResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class DeleteCouponResponse(BaseModel):
    deleted: bool
    code: str
    milestone_n: int
    message: str

