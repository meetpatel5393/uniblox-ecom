import uuid

from sqlalchemy.orm import Session

from app.core.config import settings
from app.exceptions import ConflictError, NotFoundError, UnprocessableError
from app.models.models import Coupon
from app.repositories import coupon as coupon_repo
from app.repositories import order as order_repo
from app.schemas.coupon import (
    CouponResponse,
    DeleteCouponResponse,
    GenerateCouponsRequest,
    GenerateCouponsResponse,
    MilestoneStatusResponse,
)


def get_milestone_status(db: Session, interval_n: int | None = None) -> MilestoneStatusResponse:
    """
    Computes current milestone progress based on total successfully placed orders.
    Identifies which milestones have been reached, which already have coupons,
    and which reached milestones are eligible for coupon generation.
    """
    n = interval_n or settings.coupon_every_n_orders
    total_orders = order_repo.count_all(db)
    reached = [m for m in range(n, total_orders + 1, n)] if n > 0 else []
    existing_milestones = sorted(list(coupon_repo.get_existing_milestones(db)))
    eligible = [m for m in reached if m not in existing_milestones]
    next_m = ((total_orders // n) + 1) * n if n > 0 else n
    orders_until_next = next_m - total_orders if next_m >= total_orders else 0

    return MilestoneStatusResponse(
        total_orders=total_orders,
        milestone_interval_n=n,
        default_discount_pct_x=settings.coupon_discount_pct,
        default_min_order_cents=settings.coupon_min_order_cents,
        reached_milestones=reached,
        generated_milestones=existing_milestones,
        eligible_unissued_milestones=eligible,
        next_milestone=next_m,
        orders_until_next=orders_until_next,
    )


def generate_milestone_coupons(
    db: Session,
    payload: GenerateCouponsRequest,
) -> GenerateCouponsResponse:
    """
    Admin generates milestone discount coupons.
    Strictly enforces:
    1. Order milestone must be reached (total_orders >= milestone_n).
    2. A coupon has not already been generated for that milestone.
    3. Coupons can be redeemed only once by default (max_uses=1).
    Supports auto-generation for all reached unissued milestones if milestone_n is omitted.
    """
    interval_n = payload.milestone_interval_n or settings.coupon_every_n_orders
    status = get_milestone_status(db, interval_n)
    total_orders = status.total_orders

    # Determine which milestones to generate
    if payload.milestone_n is None:
        # Auto-generation mode: scan for all reached milestones not yet generated
        if not status.eligible_unissued_milestones:
            return GenerateCouponsResponse(
                generated=0,
                message=(
                    f"No unissued order milestones reached yet. "
                    f"Total placed orders: {total_orders}. "
                    f"Next milestone #{status.next_milestone} requires {status.orders_until_next} more order(s)."
                ),
                coupons=[],
                pool_size=0,
                milestone_status=status,
            )
        milestones_to_generate = status.eligible_unissued_milestones
    else:
        target_m = payload.milestone_n
        if not payload.force:
            # Rule 1: A coupon is generated only if the configured order milestone has been reached
            if total_orders < target_m:
                raise UnprocessableError(
                    f"Milestone #{target_m} has not been reached yet. "
                    f"Only {total_orders} successfully placed order(s) recorded so far. "
                    f"{target_m - total_orders} more order(s) required to unlock this milestone coupon."
                )

            # Rule 2: A coupon has not already been generated for that milestone
            existing = coupon_repo.get_by_milestone_n(db, target_m)
            if existing:
                raise ConflictError(
                    f"A coupon has already been generated for milestone #{target_m} ({existing[0].code}). "
                    f"Each milestone order can produce only one coupon."
                )

        milestones_to_generate = [target_m]

    discount_type = payload.discount_type or "percent"
    if discount_type == "fixed":
        discount_pct = 0
        discount_amount_cents = (
            payload.discount_amount_cents
            if payload.discount_amount_cents is not None
            else 500
        )
    else:
        discount_pct = (
            payload.discount_pct
            if payload.discount_pct is not None
            else settings.coupon_discount_pct
        )
        discount_amount_cents = None

    min_order_cents = (
        payload.min_order_cents
        if payload.min_order_cents is not None
        else settings.coupon_min_order_cents
    )

    # Per requirement: "A coupon can be redeemed only once" -> default max_uses=1
    max_uses = payload.max_uses if payload.max_uses is not None else 1

    created_coupons = []
    for m in milestones_to_generate:
        code = f"MILE{m}-{uuid.uuid4().hex[:6].upper()}"
        coupon = coupon_repo.create_coupon(
            db,
            code=code,
            discount_pct=discount_pct,
            discount_type=discount_type,
            discount_amount_cents=discount_amount_cents,
            min_order_cents=min_order_cents,
            milestone_n=m,
            max_uses=max_uses,
        )
        created_coupons.append(coupon)

    db.commit()
    for c in created_coupons:
        db.refresh(c)

    rule_desc = (
        f"${(discount_amount_cents / 100):.2f} Fixed OFF"
        if discount_type == "fixed"
        else f"{discount_pct}% OFF"
    )
    first_code = created_coupons[0].code if created_coupons else ""
    updated_status = get_milestone_status(db, interval_n)

    msg = (
        f"Created {len(created_coupons)} coupon(s) [e.g. {first_code}] for reached milestone(s) "
        f"({rule_desc}, min cart ${(min_order_cents / 100):.2f}, {max_uses} use each). "
        f"Total placed orders: {total_orders}."
    )

    return GenerateCouponsResponse(
        generated=len(created_coupons),
        message=msg,
        coupons=[_to_response(c) for c in created_coupons],
        pool_size=sum(c.max_uses for c in created_coupons),
        milestone_status=updated_status,
    )


def list_coupons(db: Session) -> list[CouponResponse]:
    return [_to_response(c) for c in coupon_repo.get_all(db)]


def list_coupons_paginated(db: Session, page: int, page_size: int):
    from app.schemas.coupon import CouponListResponse
    import math
    items, total = coupon_repo.get_paginated(db, page, page_size)
    return CouponListResponse(
        items=[_to_response(c) for c in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total else 1,
    )


def delete_coupon(db: Session, code_or_id: str) -> DeleteCouponResponse:
    """
    Deletes a created coupon ONLY if it has not been used.
    If the coupon has already been redeemed, raises ConflictError (409).
    """
    coupon = coupon_repo.get_by_code_or_public_id(db, code_or_id)
    if not coupon:
        raise NotFoundError(f"Coupon '{code_or_id}' not found")

    redemptions_count = coupon_repo.count_redemptions(db, coupon.id)
    if redemptions_count > 0:
        raise ConflictError(
            f"Cannot delete coupon '{coupon.code}': it has already been redeemed by "
            f"{redemptions_count} order(s). Redeemed coupons must be preserved for accounting integrity."
        )

    code = coupon.code
    milestone_n = coupon.milestone_n
    coupon_repo.delete_coupon(db, coupon)
    db.commit()

    return DeleteCouponResponse(
        deleted=True,
        code=code,
        milestone_n=milestone_n,
        message=f"Coupon {code} (Milestone #{milestone_n}) successfully deleted.",
    )


def _to_response(coupon: Coupon) -> CouponResponse:
    redemptions_cnt = len(coupon.redemptions) if coupon.redemptions is not None else 0
    return CouponResponse(
        id=coupon.public_id,
        code=coupon.code,
        discount_pct=coupon.discount_pct,
        discount_type=getattr(coupon, "discount_type", "percent") or "percent",
        discount_amount_cents=getattr(coupon, "discount_amount_cents", None),
        min_order_cents=coupon.min_order_cents,
        milestone_n=coupon.milestone_n,
        uses_remaining=max(0, coupon.max_uses - redemptions_cnt),
        max_uses=coupon.max_uses,
        is_used=redemptions_cnt > 0,
    )
