# Architecture & Design Decisions

Every decision here is explainable in a live interview.

---

## 1. Hybrid ID Strategy: BIGINT (internal) + UUIDv7 (public)

BIGINT auto-increment PKs on every table for fast sequential B-tree inserts. Public-facing tables additionally carry a `public_id` UUIDv7 column exposed in all API responses.

**Why not UUID PKs?** Random 128-bit inserts cause random B-tree page splits — measurable write regression on high-volume join tables (`cart_items`, `order_items`).

**Why not plain integers?** Sequential IDs in URLs leak order volume (two orders a day apart reveal daily throughput by subtraction) and make scraping trivial.

**Why UUIDv7 over v4?** UUIDv7 embeds a 48-bit Unix timestamp, so secondary index lookups on `public_id` benefit from chronological clustering. Implemented in 30 lines in `app/core/utils.py` — no external dependency.

---

## 2. Money as Integer Cents

All monetary values stored as `INTEGER` (cents). No `FLOAT`, `DECIMAL`, or `NUMERIC`.

IEEE 754 cannot represent 0.10 exactly. Integer arithmetic is exact, matches the Stripe/Square industry standard, and is faster for comparisons. `Decimal` is used only for intermediate computation and always converted back to `int` before persistence.

---

## 3. `coupon_redemptions` Table (not a FK on `coupons`)

A dedicated `coupon_redemptions` table tracks usage: one row per redemption, `UNIQUE(order_id)` enforces one discount per checkout.

**Why:** A coupon can have `max_uses > 1`. A single FK column on `coupons` would cap every coupon at one use. The redemption table models the real cardinality and enables future multi-use promotions without a schema change.

**Concurrency:** A `SELECT FOR UPDATE` on the coupon row inside the checkout transaction serialises competing redemptions — only one request can read `count < max_uses` and insert at a time.

---

## 4. `UNIQUE(cart_id)` on `orders` — Natural Idempotency Key

Retrying checkout for the same cart returns the existing order, never a duplicate. No client-generated idempotency token required.

If `INSERT INTO orders` violates the unique constraint, `CheckoutService` catches it and returns the already-created order with `201`. Stock is only decremented once because the transaction rolls back on the duplicate insert path.

---

## 5. `SELECT FOR UPDATE` for Inventory and Coupon Concurrency

Checkout locks all `Product` rows in the cart (ascending `id` order to prevent deadlocks) and the `Coupon` row before any write. Stock is then decremented atomically: `UPDATE products SET stock_qty = stock_qty - :qty WHERE stock_qty >= :qty`.

| Race | Protection |
|---|---|
| Two users buy the last unit | `FOR UPDATE` serialises; second fails the availability check inside the lock |
| Same coupon used from two tabs | `FOR UPDATE` on coupon row; only one gets the last redemption slot |
| Retry / double-click checkout | `UNIQUE(cart_id)` on orders returns existing order |

**Rejected alternative:** Optimistic locking + retry. Checkout always writes — retry logic adds complexity with no throughput benefit at realistic load.

---

## 6. DB-Level `CHECK` Constraints

Every single-row business invariant is enforced at the DB layer in addition to application validation: `price_cents > 0`, `stock_qty >= 0`, `discount_cents >= 0`, `net_cents >= 0`, `discount_pct BETWEEN 1 AND 100`.

Application validation can be bypassed by migrations, admin tools, or bugs. DB constraints are the last line of defence and make the schema self-documenting.

---

## 7. Milestone Coupon Generation

Coupons are gated behind a milestone (`total_orders >= milestone_n`). A `UNIQUE(milestone_n)` DB constraint prevents duplicate issuance even under concurrent admin calls.

- **Auto-scan** (`milestone_n: null`): scans all reached, un-issued milestones and generates one coupon each. Idempotent — safe for cron.
- **Targeted** (`milestone_n: N`): validates milestone reached (else `422`), duplicate (else `409`).
- Discount uses `floor(gross * pct / 100)` — deterministic, always rounds down, `net_cents` can never go negative (also enforced by `CHECK`).
- Coupon is never consumed by a failed checkout — the transaction rolls back atomically.

---

## 8. Price Snapshot in `order_items`

`product_name` and `price_cents` are copied from `Product` into each `OrderItem` at checkout time.

Storing only `product_id` means historical order values shift every time a product is repriced — breaking receipts and refund calculations. Snapshots make order history immutable.

---

## 9. Layered Architecture: Router → Service → Repository → DB

| Layer | Responsibility |
|---|---|
| Router | HTTP parsing, response serialisation |
| Service | Business logic, transaction boundaries |
| Repository | All SQLAlchemy queries — no logic |
| Model | Schema + CHECK constraints |

Each layer has one reason to change. Services are testable without HTTP; repositories are mockable without a DB.

---

## 10. OrderStatus as Integer Constants (not Enum)

`SMALLINT` (2 bytes) with class constants (`PLACED = 1`). No SQLAlchemy `Enum` type.

Adding a new status to a PostgreSQL `ENUM` requires `ALTER TYPE` — a column lock in production. Adding an integer constant is a Python-only change with zero schema migration.

---

## 11. Error Semantics

| Code | When |
|---|---|
| `409 Conflict` | State conflict — cart already checked out, coupon exhausted |
| `422 Unprocessable` | Business-rule violation — insufficient stock, empty cart, min-order not met |
| `404 Not Found` | Entity doesn't exist |

`409` vs `422` is a deliberate distinction: clients can take targeted action (retry later vs. fix the request) without parsing the message string.

---

## 12. Coupon Deletion Guard

Coupons with any redemptions cannot be deleted (`409 Conflict`). Unredeemed coupons can be deleted cleanly.

Deleting a redeemed coupon would orphan `coupon_redemptions` rows, corrupt order receipts, and break revenue reconciliation reports.

---

## 13. How AI Was Used

Claude (claude-sonnet) generated scaffolding, models, and service code. Key redirections I made:

- **BIGINT + UUIDv7 over UUID PKs** — Claude's first version used UUID PKs on all tables including join tables. I redirected after identifying the B-tree fragmentation problem.
- **BIGINT surrogate PK on `cart_items`** over Claude's composite `(cart_id, product_id)` PK — simpler FK references, cleaner upsert logic; uniqueness enforced by `UNIQUE(cart_id, product_id)`.
- **`UNIQUE(milestone_n)` DB constraint** — Claude's initial generate logic had a TOCTOU race where two concurrent admin calls would both pass the application-level duplicate check. The fix was a DB constraint.
- **Admin report fields** — Claude's initial response schema was missing per-product breakdown, gross vs. net distinction, and coupon lifecycle stats. I specified exact fields and rewrote the repository queries.

Every line has been reviewed. I can explain any invariant, predict concurrent behaviour, or change any business rule in a live discussion.
