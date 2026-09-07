"""
Admin sales report — correctness and idempotency.
  - totals match placed orders
  - repeated GETs don't mutate state
  - coupon discounts are reflected
"""

from tests.conftest import (
    add_item,
    checkout,
    get_first_product,
    make_cart,
    make_customer,
    place_n_orders,
)


def test_report_zero_orders(client):
    r = client.get("/api/v1/admin/report")
    assert r.status_code == 200
    data = r.json()
    assert data["total_orders"] == 0
    assert data["net_revenue_cents"] == 0
    assert data["total_discount_cents"] == 0


def test_report_reflects_placed_orders(client):
    product = get_first_product(client)
    customer = make_customer(client)
    cart = make_cart(client, customer["id"])
    add_item(client, cart["id"], product["id"], qty=2)
    checkout(client, cart["id"])

    r = client.get("/api/v1/admin/report")
    data = r.json()
    assert data["total_orders"] == 1
    assert data["gross_revenue_cents"] == product["price_cents"] * 2
    assert data["total_discount_cents"] == 0


def test_report_aggregates_multiple_orders(client):
    orders = place_n_orders(client, 3)
    expected_net = sum(o["net_cents"] for o in orders)

    r = client.get("/api/v1/admin/report")
    data = r.json()
    assert data["total_orders"] == 3
    assert data["net_revenue_cents"] == expected_net


def test_report_is_idempotent(client):
    """Calling the report endpoint twice must return the same data both times."""
    place_n_orders(client, 2)

    r1 = client.get("/api/v1/admin/report")
    r2 = client.get("/api/v1/admin/report")
    assert r1.json() == r2.json()


def test_report_includes_coupon_discount(client):
    """Discount amount from coupon must appear in report's total_discount_cents."""
    from app.core.config import settings
    n = settings.coupon_every_n_orders

    place_n_orders(client, n)
    gen = client.post("/api/v1/admin/coupons/generate", json={"milestone_n": n, "force": False})
    assert gen.status_code == 201
    code = gen.json()["coupons"][0]["code"]

    product = get_first_product(client)
    customer = make_customer(client, name="Discount", email="discount@report.com")
    cart = make_cart(client, customer["id"])
    add_item(client, cart["id"], product["id"], qty=1)
    order = checkout(client, cart["id"], coupon_code=code).json()

    r = client.get("/api/v1/admin/report")
    data = r.json()
    assert data["total_discount_cents"] >= order["discount_cents"]
    assert data["total_discount_cents"] > 0
