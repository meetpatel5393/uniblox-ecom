"""Seed initial data — safe to re-run, skips if data already exists."""

from app.core.database import SessionLocal
from app.models.models import Customer, Product


def seed() -> None:
    db = SessionLocal()
    try:
        # skip if already seeded
        if db.query(Product).count() > 0:
            print("Seed data already exists, skipping.")
            return

        customers = [
            Customer(name="Alice Johnson", email="alice@example.com"),
            Customer(name="Bob Smith", email="bob@example.com"),
        ]
        db.add_all(customers)

        products = [
            Product(name="Wireless Headphones", price_cents=4999, stock_qty=50),
            Product(name="Mechanical Keyboard", price_cents=8999, stock_qty=30),
            Product(name="USB-C Hub", price_cents=2499, stock_qty=100),
            Product(name="Webcam HD 1080p", price_cents=3499, stock_qty=25),
            # limited stock item — used to test inventory concurrency
            Product(name="Limited Edition Mouse", price_cents=5999, stock_qty=3),
        ]
        db.add_all(products)

        db.commit()
        print(f"Seeded {len(customers)} customers and {len(products)} products.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
