from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import Coupon, CouponRedemption, Order, OrderItem


def get_report_stats(db: Session) -> dict:
    # ── Order-level aggregates ────────────────────────────────────────────────
    order_stats = db.query(
        func.count(Order.id).label("total_orders"),
        func.coalesce(func.sum(Order.gross_cents), 0).label("gross_revenue_cents"),
        func.coalesce(func.sum(Order.discount_cents), 0).label("total_discount_cents"),
        func.coalesce(func.sum(Order.net_cents), 0).label("net_revenue_cents"),
    ).one()

    total_items: int = db.query(
        func.coalesce(func.sum(OrderItem.qty), 0)
    ).scalar() or 0

    # ── Per-product breakdown ─────────────────────────────────────────────────
    product_rows = (
        db.query(
            OrderItem.product_name,
            func.sum(OrderItem.qty).label("qty_sold"),
            func.sum(OrderItem.subtotal_cents).label("revenue_cents"),
        )
        .group_by(OrderItem.product_name)
        .order_by(func.sum(OrderItem.qty).desc())
        .all()
    )

    # ── Coupon lifecycle stats ────────────────────────────────────────────────
    coupons_generated: int = db.query(func.count(Coupon.id)).scalar() or 0
    coupons_redeemed: int = db.query(func.count(CouponRedemption.id)).scalar() or 0

    # A coupon is "available" if its redemption count is still below max_uses
    redemption_counts_subq = (
        db.query(
            CouponRedemption.coupon_id,
            func.count(CouponRedemption.id).label("redemption_count"),
        )
        .group_by(CouponRedemption.coupon_id)
        .subquery()
    )
    coupons_available: int = (
        db.query(func.count(Coupon.id))
        .outerjoin(
            redemption_counts_subq,
            redemption_counts_subq.c.coupon_id == Coupon.id,
        )
        .filter(
            func.coalesce(redemption_counts_subq.c.redemption_count, 0) < Coupon.max_uses
        )
        .scalar()
        or 0
    )

    redeemed_codes = (
        db.query(Coupon.code)
        .join(CouponRedemption, CouponRedemption.coupon_id == Coupon.id)
        .distinct()
        .all()
    )

    return {
        "total_orders": order_stats.total_orders,
        "total_items_purchased": int(total_items),
        "gross_revenue_cents": order_stats.gross_revenue_cents,
        "total_discount_cents": order_stats.total_discount_cents,
        "net_revenue_cents": order_stats.net_revenue_cents,
        "products_sold": [
            {
                "product_name": row.product_name,
                "qty_sold": int(row.qty_sold),
                "revenue_cents": int(row.revenue_cents),
            }
            for row in product_rows
        ],
        "coupons_generated": coupons_generated,
        "coupons_available": coupons_available,
        "coupons_redeemed": coupons_redeemed,
        "discount_codes_used": [row.code for row in redeemed_codes],
    }
