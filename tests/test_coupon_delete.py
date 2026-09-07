import uuid
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import SessionLocal
from app.models.models import Coupon, Customer, Cart, Order, OrderStatus
from app.repositories import coupon as coupon_repo

client = TestClient(app)


def test_delete_unredeemed_coupon():
    db = SessionLocal()
    try:
        # Create an unredeemed coupon
        unique_code = f"TESTDEL-{uuid.uuid4().hex[:6].upper()}"
        coupon = coupon_repo.create_coupon(
            db,
            code=unique_code,
            discount_pct=15,
            min_order_cents=1000,
            milestone_n=999,
            max_uses=1,
        )
        db.commit()
        code = coupon.code

        # Delete it via endpoint
        response = client.delete(f"/api/v1/admin/coupons/{code}")
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["deleted"] is True
        assert data["code"] == code

        # Verify it is deleted in DB
        db_coupon = coupon_repo.get_by_code(db, code)
        assert db_coupon is None

        # Verify second delete returns 404
        response_404 = client.delete(f"/api/v1/admin/coupons/{code}")
        assert response_404.status_code == 404
    finally:
        db.close()


def test_cannot_delete_used_coupon():
    db = SessionLocal()
    try:
        # Find or create a coupon and redeem it
        unique_code = f"TESTUSED-{uuid.uuid4().hex[:6].upper()}"
        coupon = coupon_repo.create_coupon(
            db,
            code=unique_code,
            discount_pct=10,
            min_order_cents=0,
            milestone_n=998,
            max_uses=1,
        )
        db.flush()

        # Get or create customer
        customer = db.query(Customer).first()
        if not customer:
            customer = Customer(email="test_del@example.com", name="Test Del Customer")
            db.add(customer)
            db.flush()

        # Create cart and order to redeem
        cart = Cart(customer_id=customer.id, checked_out=True)
        db.add(cart)
        db.flush()

        order = Order(
            customer_id=customer.id,
            cart_id=cart.id,
            coupon_id=coupon.id,
            status=OrderStatus.PLACED,
            gross_cents=2000,
            discount_cents=200,
            net_cents=1800,
            currency="USD",
        )
        db.add(order)
        db.flush()

        coupon_repo.create_redemption(
            db,
            coupon_id=coupon.id,
            order_id=order.id,
            customer_id=customer.id,
        )
        db.commit()

        # Try to delete the redeemed coupon
        response = client.delete(f"/api/v1/admin/coupons/{coupon.code}")
        assert response.status_code == 409, response.text
        err = response.json()
        assert "already been redeemed" in err["detail"]

        # Ensure coupon still exists in DB
        db_coupon = coupon_repo.get_by_code(db, coupon.code)
        assert db_coupon is not None
    finally:
        db.close()
