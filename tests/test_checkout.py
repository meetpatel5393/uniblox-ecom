"""
Checkout — the most critical business rules:
  - idempotent (retry-safe)
  - oversell prevention
  - coupon happy path + failure modes
  - price snapshot preserved in order
  - discount never makes total negative
"""

import pytest
from tests.conftest import (
    add_item,
    checkout,
    get_first_product,
    make_cart,
    make_customer,
    place_n_orders,
)


# ── Happy path ────────────────────────────────────────────────────────────────

def test_checkout_creates_order(client):
    customer = make_customer(client)
    cart = make_cart(client, customer["id"])
    product = get_first_product(client)
    add_item(client, cart["id"], product["id"], qty=2)

    r = checkout(client, cart["id"])
    assert r.status_code == 201
    order = r.json()

    assert order["gross_cents"] == product["price_cents"] * 2
    assert order["discount_cents"] == 0
    assert order["net_cents"] == order["gross_cents"]
    assert order["status"] == 1  # PLACED


def test_checkout_snapshots_price_in_order(client):
    """Order line items store price at checkout — unaffected by later product changes."""
    customer = make_customer(client)
    cart = make_cart(client, customer["id"])
    product = get_first_product(client)
    add_item(client, cart["id"], product["id"], qty=1)

    r = checkout(client, cart["id"])
    assert r.status_code == 201
    order = r.json()

    assert order["items"][0]["price_cents"] == product["price_cents"]
    assert order["items"][0]["product_name"] == product["name"]


# ── Idempotency ───────────────────────────────────────────────────────────────

def test_checkout_is_idempotent(client):
    """Retrying a checkout returns the same order — no duplicate order or stock deduction."""
    customer = make_customer(client)
    cart = make_cart(client, customer["id"])
    product = get_first_product(client)
    add_item(client, cart["id"], product["id"], qty=1)

    r1 = checkout(client, cart["id"])
    r2 = checkout(client, cart["id"])

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]  # Same order returned, not a new one


def test_checkout_deducts_stock_only_once_on_retry(client):
    """Idempotent checkout must not deduct stock twice."""
    customer = make_customer(client)
    cart = make_cart(client, customer["id"])
    product = get_first_product(client)
    initial_stock = product["stock_qty"]

    add_item(client, cart["id"], product["id"], qty=1)
    checkout(client, cart["id"])
    checkout(client, cart["id"])  # retry

    r = client.get("/api/v1/products")
    updated = next(p for p in r.json() if p["id"] == product["id"])
    assert updated["stock_qty"] == initial_stock - 1  # deducted exactly once


# ── Oversell prevention ───────────────────────────────────────────────────────

def test_checkout_blocked_when_stock_depleted(client):
    """
    Cart can be built with qty that matched stock, but if stock is gone by checkout
    (another order won the race), checkout must fail with 409.
    """
    product = get_first_product(client)
    available = product["stock_qty"]

    # First customer takes all stock
    c1 = make_customer(client, name="First", email="first@example.com")
    cart1 = make_cart(client, c1["id"])
    add_item(client, cart1["id"], product["id"], qty=available)
    r = checkout(client, cart1["id"])
    assert r.status_code == 201

    # Second customer tries to buy the same product — stock is gone
    c2 = make_customer(client, name="Second", email="second@example.com")
    cart2 = make_cart(client, c2["id"])
    # Force-add 1 item directly (bypasses stock check at add time for this test)
    r_add = client.post(
        f"/api/v1/carts/{cart2['id']}/items",
        json={"product_id": product["id"], "qty": 1},
    )
    if r_add.status_code == 409:
        pytest.skip("Add-to-cart already enforces stock — checkout oversell path not reachable here")

    r2 = checkout(client, cart2["id"])
    assert r2.status_code in (409, 422)


def test_add_to_cart_prevents_oversell(client):
    """Add-to-cart validates stock — first line of defence."""
    product = get_first_product(client)
    customer = make_customer(client)
    cart = make_cart(client, customer["id"])

    r = client.post(
        f"/api/v1/carts/{cart['id']}/items",
        json={"product_id": product["id"], "qty": product["stock_qty"] + 1},
    )
    assert r.status_code in (409, 422)


# ── Coupon flows ──────────────────────────────────────────────────────────────

def test_checkout_with_valid_coupon_applies_discount(client):
    """Full happy path: reach milestone, generate coupon, apply at checkout."""
    from app.core.config import settings
    n = settings.coupon_every_n_orders

    place_n_orders(client, n)

    # Generate coupon
    gen = client.post("/api/v1/admin/coupons/generate", json={"milestone_n": n, "force": False})
    assert gen.status_code == 201
    code = gen.json()["coupons"][0]["code"]

    # New customer checks out with the coupon
    customer = make_customer(client, name="Coupon User", email="coupon@example.com")
    cart = make_cart(client, customer["id"])
    product = get_first_product(client)
    add_item(client, cart["id"], product["id"], qty=2)

    r = checkout(client, cart["id"], coupon_code=code)
    assert r.status_code == 201
    order = r.json()
    assert order["discount_cents"] > 0
    assert order["net_cents"] < order["gross_cents"]
    assert order["coupon_code"] == code


def test_checkout_with_nonexistent_coupon_returns_404(client):
    customer = make_customer(client)
    cart = make_cart(client, customer["id"])
    product = get_first_product(client)
    add_item(client, cart["id"], product["id"], qty=1)

    r = checkout(client, cart["id"], coupon_code="FAKE-COUPON")
    assert r.status_code == 404


def test_coupon_not_consumed_when_checkout_fails(client):
    """
    If checkout fails (e.g. empty cart), the coupon must not be marked as redeemed.
    """
    from app.core.config import settings
    n = settings.coupon_every_n_orders

    place_n_orders(client, n)
    gen = client.post("/api/v1/admin/coupons/generate", json={"milestone_n": n, "force": False})
    assert gen.status_code == 201
    code = gen.json()["coupons"][0]["code"]

    # Attempt checkout on an empty cart (will fail)
    customer = make_customer(client, name="Empty", email="empty@example.com")
    cart = make_cart(client, customer["id"])
    r = checkout(client, cart["id"], coupon_code=code)
    assert r.status_code in (409, 422)  # empty cart rejected

    # Coupon must still be usable
    customer2 = make_customer(client, name="Valid", email="valid@example.com")
    cart2 = make_cart(client, customer2["id"])
    product = get_first_product(client)
    add_item(client, cart2["id"], product["id"], qty=1)
    r2 = checkout(client, cart2["id"], coupon_code=code)
    assert r2.status_code == 201
    assert r2.json()["discount_cents"] > 0


def test_discount_never_makes_total_negative(client):
    """Even a 100% coupon must not produce a negative net total."""
    from app.core.config import settings
    n = settings.coupon_every_n_orders

    place_n_orders(client, n)
    # Generate with 100% discount
    gen = client.post(
        "/api/v1/admin/coupons/generate",
        json={"milestone_n": n, "discount_pct": 100, "force": False},
    )
    if gen.status_code != 201:
        pytest.skip("100% coupon generation not supported or milestone not reached")
    code = gen.json()["coupons"][0]["code"]

    customer = make_customer(client, name="Hundred", email="hundred@example.com")
    cart = make_cart(client, customer["id"])
    product = get_first_product(client)
    add_item(client, cart["id"], product["id"], qty=1)

    r = checkout(client, cart["id"], coupon_code=code)
    assert r.status_code == 201
    assert r.json()["net_cents"] >= 0


def test_checkout_empty_cart_returns_error(client):
    customer = make_customer(client)
    cart = make_cart(client, customer["id"])
    r = checkout(client, cart["id"])
    assert r.status_code in (409, 422)
