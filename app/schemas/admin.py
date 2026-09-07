from pydantic import BaseModel


class ProductSoldItem(BaseModel):
    """Per-product sales breakdown in the admin report."""

    product_name: str
    qty_sold: int
    revenue_cents: int  # net contribution (after proportional discount)


class AdminReportResponse(BaseModel):
    # Order totals
    total_orders: int
    total_items_purchased: int

    # Revenue breakdown (all in integer cents)
    gross_revenue_cents: int       # sum of order gross totals before discounts
    total_discount_cents: int      # sum of all discounts granted
    net_revenue_cents: int         # sum of order net totals after discounts

    # Per-product breakdown
    products_sold: list[ProductSoldItem]

    # Coupon lifecycle
    coupons_generated: int         # total coupons ever created
    coupons_available: int         # coupons with at least one remaining use
    coupons_redeemed: int          # total redemption events (one per order that used a coupon)
    discount_codes_used: list[str] # distinct coupon codes that have been redeemed
