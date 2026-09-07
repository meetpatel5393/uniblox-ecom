"""
Coupon business rules:
  - milestone gate enforcement (can't generate without N orders)
  - duplicate prevention (same milestone → 409)
  - force flag bypasses gate
  - exhausted coupon rejected at checkout
  - milestone status tracks correctly
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


def _generate(client, milestone_n, *, force=False, **kwargs):
    payload = {"milestone_n": milestone_n, "force": force, **kwargs}
    return client.post("/api/v1/admin/coupons/generate", json=payload)


# ── Milestone gate ────────────────────────────────────────────────────────────

def test_generate_coupon_before_milestone_returns_422(client):
    """No orders placed — generating coupon must be rejected."""
    from app.core.config import settings
    n = settings.coupon_every_n_orders

    r = _generate(client, n, force=False)
    assert r.status_code in (409, 422)


def test_generate_coupon_after_milestone_succeeds(client):
    from app.core.config import settings
    n = settings.coupon_every_n_orders

    place_n_orders(client, n)
    r = _generate(client, n)
    assert r.status_code == 201
    data = r.json()
    assert len(data["coupons"]) >= 1
    assert data["coupons"][0]["code"]


def test_generate_same_milestone_twice_returns_409(client):
    """Second generate for the same milestone is a conflict."""
    from app.core.config import settings
    n = settings.coupon_every_n_orders

    place_n_orders(client, n)
    r1 = _generate(client, n)
    assert r1.status_code == 201

    r2 = _generate(client, n)
    assert r2.status_code == 409


def test_force_flag_bypasses_milestone_gate(client):
    """force=True allows coupon generation regardless of order count."""
    from app.core.config import settings
    n = settings.coupon_every_n_orders

    # No orders placed — would normally fail
    r = _generate(client, n, force=True)
    assert r.status_code == 201
    assert r.json()["coupons"][0]["code"]


# ── Milestone status ──────────────────────────────────────────────────────────

def test_milestone_status_before_any_orders(client):
    r = client.get("/api/v1/admin/coupons/milestones")
    assert r.status_code == 200
    data = r.json()
    assert data["total_orders"] == 0
    assert data["reached_milestones"] == []
    assert data["eligible_unissued_milestones"] == []


def test_milestone_status_after_n_orders(client):
    from app.core.config import settings
    n = settings.coupon_every_n_orders

    place_n_orders(client, n)
    r = client.get("/api/v1/admin/coupons/milestones")
    assert r.status_code == 200
    data = r.json()
    assert data["total_orders"] == n
    assert len(data["reached_milestones"]) >= 1
    assert len(data["eligible_unissued_milestones"]) >= 1


def test_milestone_status_after_coupon_generated(client):
    from app.core.config import settings
    n = settings.coupon_every_n_orders

    place_n_orders(client, n)
    _generate(client, n)

    r = client.get("/api/v1/admin/coupons/milestones")
    data = r.json()
    assert data["eligible_unissued_milestones"] == []  # consumed the one eligible slot


# ── Coupon exhaustion ─────────────────────────────────────────────────────────

def test_exhausted_coupon_rejected_at_checkout(client):
    """After max_uses are consumed, the coupon must be rejected."""
    from app.core.config import settings
    n = settings.coupon_every_n_orders

    place_n_orders(client, n)
    gen = _generate(client, n, max_uses=1)
    assert gen.status_code == 201
    code = gen.json()["coupons"][0]["code"]

    # First use — succeeds
    c1 = make_customer(client, name="First", email="first@coupon.com")
    cart1 = make_cart(client, c1["id"])
    product = get_first_product(client)
    add_item(client, cart1["id"], product["id"], qty=1)
    r1 = checkout(client, cart1["id"], coupon_code=code)
    assert r1.status_code == 201

    # Second use — must fail (exhausted)
    c2 = make_customer(client, name="Second", email="second@coupon.com")
    cart2 = make_cart(client, c2["id"])
    add_item(client, cart2["id"], product["id"], qty=1)
    r2 = checkout(client, cart2["id"], coupon_code=code)
    assert r2.status_code in (409, 422)


def test_coupon_with_multiple_uses(client):
    """max_uses=2 coupon should be accepted twice then rejected on the third."""
    from app.core.config import settings
    n = settings.coupon_every_n_orders

    place_n_orders(client, n)
    gen = _generate(client, n, max_uses=2, force=False)
    assert gen.status_code == 201
    code = gen.json()["coupons"][0]["code"]
    product = get_first_product(client)

    for i in range(2):
        c = make_customer(client, name=f"User{i}", email=f"mc{i}@example.com")
        cart = make_cart(client, c["id"])
        add_item(client, cart["id"], product["id"], qty=1)
        r = checkout(client, cart["id"], coupon_code=code)
        assert r.status_code == 201, f"Use {i+1} failed"

    # Third use must fail
    c3 = make_customer(client, name="Extra", email="extra@example.com")
    cart3 = make_cart(client, c3["id"])
    add_item(client, cart3["id"], product["id"], qty=1)
    r3 = checkout(client, cart3["id"], coupon_code=code)
    assert r3.status_code in (409, 422)


# ── Delete coupon ─────────────────────────────────────────────────────────────

def test_delete_coupon(client):
    from app.core.config import settings
    n = settings.coupon_every_n_orders

    place_n_orders(client, n)
    gen = _generate(client, n)
    coupon = gen.json()["coupons"][0]
    code = coupon["code"]

    r = client.delete(f"/api/v1/admin/coupons/{code}")
    assert r.status_code == 200

    # Deleted coupon no longer accepted at checkout
    customer = make_customer(client)
    cart = make_cart(client, customer["id"])
    product = get_first_product(client)
    add_item(client, cart["id"], product["id"], qty=1)
    r2 = checkout(client, cart["id"], coupon_code=code)
    assert r2.status_code == 404
