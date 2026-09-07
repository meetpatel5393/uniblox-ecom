# uniblox-ecom

An e-commerce backend that handles cart management, checkout, and a milestone-based coupon rewards system — built with FastAPI, SQLAlchemy 2, and PostgreSQL.

---

## Table of Contents

- [Live Demo](#live-demo)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Local Setup](#local-setup)
- [Environment Variables](#environment-variables)
- [Database Migrations](#database-migrations)
- [Seed Data](#seed-data)
- [Running the Server](#running-the-server)
- [API Documentation](#api-documentation)
- [Running Tests](#running-tests)
- [Project Structure](#project-structure)
- [Key Design Decisions](#key-design-decisions)

---

## Live Demo

| Resource | URL |
|---|---|
| API base | `https://uniblox-ecom-production.up.railway.app/api/v1` |
| Swagger UI | `https://uniblox-ecom-production.up.railway.app/docs` |
| ReDoc | `https://uniblox-ecom-production.up.railway.app/redoc` |
| Health check | `https://uniblox-ecom-production.up.railway.app/health` |

---

## Features

- **Cart lifecycle** — create, add/update/remove items, view totals
- **Idempotent checkout** — retrying the same cart always returns the same order; never double-charges inventory
- **Oversell prevention** — `SELECT FOR UPDATE` locks stock rows before decrement; enforced at both add-to-cart and checkout
- **Milestone coupon system** — every N orders (default: 5) an admin can generate a coupon worth X% off (default: 10%); supports single-use and multi-use codes
- **Admin report** — gross revenue, net revenue, per-product sales, coupon lifecycle stats
- **Price snapshot** — order line items capture name and price at checkout time, immune to later product changes
- **Money as integer cents** — no floating-point arithmetic; all amounts are stored as `INTEGER` cents

---

## Tech Stack

| Layer | Choice |
|---|---|
| Runtime | Python 3.12+ |
| Web framework | FastAPI 0.115 |
| ORM | SQLAlchemy 2.0 (synchronous, thread-pool model) |
| DB migrations | Alembic |
| Database | PostgreSQL 16 |
| Testing | pytest + FastAPI TestClient + SQLite in-memory |
| Deployment | Railway (managed PostgreSQL + Python runtime) |

---

## Local Setup

### Prerequisites

- Python 3.12 or later
- PostgreSQL 14 or later (running locally, or use the Railway URL directly)
- `pip`

### Install dependencies

```bash
cd uniblox
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## Environment Variables

Copy the example file and fill in your values:

```bash
cp .env.example .env
```

`.env.example`:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/uniblox

# Coupon system
COUPON_EVERY_N_ORDERS=5        # generate a coupon after every N successfully placed orders
COUPON_DISCOUNT_PCT=10         # default discount percentage (x in the spec)
COUPON_MIN_ORDER_CENTS=500     # minimum cart value to apply a coupon (500 = $5.00)
CURRENCY=USD                   # ISO 4217 currency code stored on each order
```

> **Note:** `DATABASE_URL` is the only required variable. All others have defaults.

---

## Database Migrations

Run all migrations against the configured database:

```bash
alembic upgrade head
```

To create a new migration after model changes:

```bash
alembic revision --autogenerate -m "describe_the_change"
```

Migration history:

| Revision | Description |
|---|---|
| `0001` | Initial schema (customers, products, carts, cart_items, orders, order_items, coupons, coupon_redemptions) |
| `0004` | Add `discount_type` and `discount_amount_cents` to coupons |

---

## Seed Data

Populate the database with sample customers and products:

```bash
python seed.py
```

This is idempotent — safe to run multiple times. It skips seeding if products already exist.

Seeded data:
- 2 customers (Alice Johnson, Bob Smith)
- 5 products (Wireless Headphones $49.99, Mechanical Keyboard $89.99, USB-C Hub $24.99, Webcam HD $34.99, Limited Edition Mouse $59.99 — qty: 3, for concurrency testing)

---

## Running the Server

```bash
uvicorn app.main:app --reload --port 8000
```

The server starts at `http://localhost:8000`.

For production (no auto-reload):

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## API Documentation

FastAPI generates interactive documentation automatically:

| UI | URL |
|---|---|
| Swagger UI (try it live) | http://localhost:8000/docs |
| ReDoc (clean reference) | http://localhost:8000/redoc |
| OpenAPI JSON | http://localhost:8000/openapi.json |

### Quick endpoint reference

#### Customers
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/customers` | Create a customer |
| `GET` | `/api/v1/customers` | List all customers |
| `GET` | `/api/v1/customers/{id}` | Get a customer by ID |

#### Products
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/products` | List all products (with current stock) |

#### Carts
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/carts` | Create a cart for a customer |
| `GET` | `/api/v1/carts/{id}` | View cart with line totals |
| `POST` | `/api/v1/carts/{id}/items` | Add a product (merges qty if already present) |
| `PATCH` | `/api/v1/carts/{id}/items/{product_id}` | Update item quantity |
| `DELETE` | `/api/v1/carts/{id}/items/{product_id}` | Remove an item |
| `POST` | `/api/v1/carts/{id}/checkout` | Place an order (idempotent) |

#### Orders
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/orders` | List orders (paginated: `?page=1&page_size=10`) |
| `GET` | `/api/v1/orders/{id}` | Get a single order with line items |

#### Admin
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/admin/coupons/generate` | Generate milestone coupon(s) |
| `GET` | `/api/v1/admin/coupons/milestones` | View milestone progress and coupon status |
| `DELETE` | `/api/v1/admin/coupons/{code_or_id}` | Delete an unredeemed coupon |
| `GET` | `/api/v1/admin/report` | Sales report (revenue, per-product, coupons) |

### Example: full checkout flow

```bash
# 1. Create a customer
curl -X POST http://localhost:8000/api/v1/customers \
  -H "Content-Type: application/json" \
  -d '{"name": "Jane Doe", "email": "jane@example.com"}'

# 2. Create a cart
curl -X POST http://localhost:8000/api/v1/carts \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "<customer_id>"}'

# 3. Add a product
curl -X POST http://localhost:8000/api/v1/carts/<cart_id>/items \
  -H "Content-Type: application/json" \
  -d '{"product_id": "<product_id>", "qty": 2}'

# 4. Checkout (no coupon)
curl -X POST http://localhost:8000/api/v1/carts/<cart_id>/checkout \
  -H "Content-Type: application/json" \
  -d '{}'

# 5. Generate a coupon (after 5 orders)
curl -X POST http://localhost:8000/api/v1/admin/coupons/generate \
  -H "Content-Type: application/json" \
  -d '{"milestone_n": 5}'

# 6. Checkout with coupon
curl -X POST http://localhost:8000/api/v1/carts/<new_cart_id>/checkout \
  -H "Content-Type: application/json" \
  -d '{"coupon_code": "<code>"}'
```

---

## Running Tests

Tests use an **SQLite in-memory database** — no PostgreSQL connection needed, no `.env` required.

```bash
pytest tests/ -v
```

To exclude the one test file that requires a live PostgreSQL connection:

```bash
pytest tests/ -v --ignore=tests/test_coupon_delete.py
```

### Test coverage

| File | Tests | What it covers |
|---|---|---|
| `test_customers.py` | 6 | Create, duplicate email 409, missing field 422, get, 404, list |
| `test_carts.py` | 10 | Create, add, update qty, remove, oversell guard, merge qty |
| `test_checkout.py` | 9 | Happy path, price snapshot, idempotency, coupon apply/reject, discount floor |
| `test_coupons.py` | 10 | Milestone gate, duplicate 409, force flag, exhaustion, multi-use, delete |
| `test_orders.py` | 6 | Get by ID, 404, paginated list, page 2 no-overlap |
| `test_admin_report.py` | 5 | Zero orders, single order totals, aggregation, idempotent reads, discount |
| `test_concurrency.py` | 4 | Idempotent retry, stock deducted once, oversell prevention, single-use coupon |
| **Total** | **53 passed** | |

> `test_coupon_delete.py` hits the real PostgreSQL database directly (via `SessionLocal`) and is excluded from the default test run. Run it separately with a configured `.env`.

---

## Project Structure

```
app/
├── api/
│   └── v1/
│       ├── endpoints/       # HTTP layer: parse request, call service, return response
│       │   ├── admin.py
│       │   ├── carts.py
│       │   ├── customers.py
│       │   ├── orders.py
│       │   └── products.py
│       └── router.py        # mounts all endpoint routers under /api/v1
├── core/
│   ├── config.py            # pydantic-settings: reads .env
│   ├── database.py          # engine, SessionLocal, Base, get_db
│   ├── errors.py            # HTTP exception helpers (404, 409, 422)
│   └── utils.py             # uuid7() implementation
├── models/
│   └── models.py            # SQLAlchemy ORM models + DB-level CHECK constraints
├── repositories/            # All SQLAlchemy queries — no business logic
│   ├── admin.py
│   ├── cart.py
│   ├── coupon.py
│   ├── customer.py
│   └── order.py
├── schemas/                 # Pydantic request/response models
│   ├── admin.py
│   ├── cart.py
│   ├── coupon.py
│   ├── customer.py
│   └── order.py
├── services/                # Business logic and transaction boundaries
│   ├── admin.py
│   ├── cart.py
│   ├── checkout.py
│   ├── coupon.py
│   ├── customer.py
│   └── order.py
└── main.py                  # FastAPI app, middleware, router mount

alembic/                     # DB migration scripts
tests/                       # pytest test suite (SQLite in-memory)
seed.py                      # Sample data loader
DECISIONS.md                 # Architecture and design decision log
```

---

## Key Design Decisions

See [`DECISIONS.md`](DECISIONS.md) for the full reasoning behind every significant choice. Highlights:

- **BIGINT PK + UUIDv7 public_id** — fast internal joins, opaque external IDs, no business intelligence leakage
- **Integer cents** — exact arithmetic; no IEEE 754 rounding errors
- **`UNIQUE(cart_id)` on orders** — natural idempotency key; retrying checkout never creates a duplicate order
- **`SELECT FOR UPDATE`** — serialises concurrent checkout on product rows and coupon rows; prevents oversell and coupon double-spend
- **`CHECK` constraints** — business invariants enforced at the DB layer regardless of caller
- **Milestone coupon gate** — coupon generation requires `total_orders >= milestone_n`; duplicate milestone generates a `409 Conflict`
