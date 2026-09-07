"""
Test configuration — creates a fresh SQLite in-memory database for EACH test,
wiring FastAPI's dependency injection to use it instead of production PostgreSQL.
No external services needed.

Isolation strategy: new engine + new DB per test.
With sqlite:///:memory: + StaticPool, each engine owns its own in-memory database,
so tests are perfectly isolated without needing transaction rollbacks.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# ── SQLite compatibility patches (applied before any model import) ─────────────
# SQLite only auto-increments INTEGER PRIMARY KEY, not BIGINT PRIMARY KEY.
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
SQLiteTypeCompiler.visit_BIGINT = lambda self, type_, **kw: "INTEGER"

# PostgreSQL UUID type → plain TEXT on SQLite.
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.dialects.sqlite.base import SQLiteDialect
from sqlalchemy import Text
SQLiteDialect.colspecs = {**SQLiteDialect.colspecs, PG_UUID: Text}

from app.core.database import Base, get_db
from app.main import app


def _make_engine():
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def _seed_products(session: Session):
    from app.models.models import Product
    from app.core.utils import uuid7
    products = [
        Product(public_id=uuid7(), name="Laptop",     price_cents=99999,  stock_qty=50),
        Product(public_id=uuid7(), name="Mouse",      price_cents=2999,   stock_qty=200),
        Product(public_id=uuid7(), name="Keyboard",   price_cents=7999,   stock_qty=150),
        Product(public_id=uuid7(), name="Monitor",    price_cents=34999,  stock_qty=30),
        Product(public_id=uuid7(), name="Headphones", price_cents=14999,  stock_qty=100),
    ]
    session.add_all(products)
    session.commit()


@pytest.fixture()
def db():
    """
    Fresh SQLite in-memory database per test.
    Each engine instance owns its own isolated DB — no rollback needed.
    """
    engine = _make_engine()
    Base.metadata.create_all(bind=engine)
    session = Session(engine)
    _seed_products(session)
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def client(db):
    """TestClient wired to the per-test in-memory DB session."""
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


# ── Reusable factory helpers ──────────────────────────────────────────────────

def make_customer(client, name="Alice", email="alice@example.com"):
    r = client.post("/api/v1/customers", json={"name": name, "email": email})
    assert r.status_code == 201, f"make_customer failed: {r.json()}"
    return r.json()


def make_cart(client, customer_id):
    r = client.post("/api/v1/carts", json={"customer_id": customer_id})
    assert r.status_code == 201, f"make_cart failed: {r.json()}"
    return r.json()


def get_first_product(client):
    r = client.get("/api/v1/products")
    assert r.status_code == 200
    products = r.json()
    assert products, "Seed data missing"
    return products[0]


def add_item(client, cart_id, product_id, qty=1):
    r = client.post(
        f"/api/v1/carts/{cart_id}/items",
        json={"product_id": product_id, "qty": qty},
    )
    assert r.status_code == 201, f"add_item failed: {r.json()}"
    return r.json()


def checkout(client, cart_id, coupon_code=None):
    return client.post(f"/api/v1/carts/{cart_id}/checkout", json={"coupon_code": coupon_code})


def place_n_orders(client, n):
    """Place n independent orders (each with a unique customer + cart)."""
    orders = []
    for i in range(n):
        c = make_customer(client, name=f"User{i}", email=f"user{i}@example.com")
        cart = make_cart(client, c["id"])
        product = get_first_product(client)
        add_item(client, cart["id"], product["id"], qty=1)
        r = checkout(client, cart["id"])
        assert r.status_code == 201, f"place_n_orders order {i} failed: {r.json()}"
        orders.append(r.json())
    return orders
