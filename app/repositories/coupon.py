import uuid

from sqlalchemy.orm import Session, selectinload

from app.models.models import Coupon, CouponRedemption


def get_by_code(db: Session, code: str) -> Coupon | None:
    return (
        db.query(Coupon)
        .options(selectinload(Coupon.redemptions))
        .filter(Coupon.code == code)
        .first()
    )


def get_by_code_for_update(db: Session, code: str) -> Coupon | None:
    """Lock the coupon row before counting redemptions — prevents parallel coupon-exhaust exploit."""
    return (
        db.query(Coupon)
        .filter(Coupon.code == code)
        .with_for_update()
        .first()
    )


def count_redemptions(db: Session, coupon_id: int) -> int:
    return (
        db.query(CouponRedemption)
        .filter(CouponRedemption.coupon_id == coupon_id)
        .count()
    )


def get_existing_milestones(db: Session) -> set[int]:
    rows = db.query(Coupon.milestone_n).all()
    return {r.milestone_n for r in rows}


def get_by_milestone_n(db: Session, milestone_n: int) -> list[Coupon]:
    return (
        db.query(Coupon)
        .options(selectinload(Coupon.redemptions))
        .filter(Coupon.milestone_n == milestone_n)
        .all()
    )


def count_available_for_milestone(db: Session, milestone_n: int) -> int:
    """Sum remaining uses across all coupons for a milestone (max_uses - redemptions so far)."""
    from sqlalchemy import func

    coupons = db.query(Coupon).filter(Coupon.milestone_n == milestone_n).all()
    total = 0
    for c in coupons:
        redeemed = db.query(CouponRedemption).filter(CouponRedemption.coupon_id == c.id).count()
        remaining = c.max_uses - redeemed
        if remaining > 0:
            total += remaining
    return total


def create_coupon(
    db: Session,
    *,
    code: str,
    discount_pct: int = 0,
    discount_type: str = "percent",
    discount_amount_cents: int | None = None,
    min_order_cents: int,
    milestone_n: int,
    max_uses: int = 1,
) -> Coupon:
    coupon = Coupon(
        code=code,
        discount_pct=discount_pct,
        discount_type=discount_type,
        discount_amount_cents=discount_amount_cents,
        min_order_cents=min_order_cents,
        milestone_n=milestone_n,
        max_uses=max_uses,
    )
    db.add(coupon)
    return coupon


def create_redemption(
    db: Session, *, coupon_id: int, order_id: int, customer_id: int
) -> CouponRedemption:
    redemption = CouponRedemption(
        coupon_id=coupon_id,
        order_id=order_id,
        customer_id=customer_id,
    )
    db.add(redemption)
    return redemption


def get_all(db: Session) -> list[Coupon]:
    return (
        db.query(Coupon)
        .options(selectinload(Coupon.redemptions))
        .order_by(Coupon.milestone_n)
        .all()
    )


def get_by_code_or_public_id(db: Session, code_or_id: str) -> Coupon | None:
    try:
        val = uuid.UUID(code_or_id)
        coupon = (
            db.query(Coupon)
            .options(selectinload(Coupon.redemptions))
            .filter(Coupon.public_id == val)
            .first()
        )
        if coupon:
            return coupon
    except ValueError:
        pass

    return (
        db.query(Coupon)
        .options(selectinload(Coupon.redemptions))
        .filter(Coupon.code == code_or_id.strip().upper())
        .first()
    )


def delete_coupon(db: Session, coupon: Coupon) -> None:
    db.delete(coupon)
