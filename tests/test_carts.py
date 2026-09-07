"""Cart lifecycle — create, add items, update qty, remove items."""

from tests.conftest import add_item, get_first_product, make_cart, make_customer


def test_create_cart_success(client):
    customer = make_customer(client)
    r = client.post("/api/v1/carts", json={"customer_id": customer["id"]})
    assert r.status_code == 201
    data = r.json()
    assert data["items"] == []
    assert data["checked_out"] is False


def test_create_cart_unknown_customer_returns_404(client):
    r = client.post("/api/v1/carts", json={"customer_id": "00000000-0000-0000-0000-000000000000"})
    assert r.status_code == 404


def test_get_cart(client):
    customer = make_customer(client)
    cart = make_cart(client, customer["id"])
    r = client.get(f"/api/v1/carts/{cart['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == cart["id"]


def test_get_cart_not_found_returns_404(client):
    r = client.get("/api/v1/carts/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


def test_add_item_to_cart(client):
    customer = make_customer(client)
    cart = make_cart(client, customer["id"])
    product = get_first_product(client)
    r = client.post(
        f"/api/v1/carts/{cart['id']}/items",
        json={"product_id": product["id"], "qty": 2},
    )
    assert r.status_code == 201
    data = r.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["qty"] == 2
    assert data["total_cents"] == product["price_cents"] * 2


def test_add_item_unknown_product_returns_404(client):
    customer = make_customer(client)
    cart = make_cart(client, customer["id"])
    r = client.post(
        f"/api/v1/carts/{cart['id']}/items",
        json={"product_id": "00000000-0000-0000-0000-000000000000", "qty": 1},
    )
    assert r.status_code == 404


def test_add_item_exceeds_stock_returns_error(client):
    customer = make_customer(client)
    cart = make_cart(client, customer["id"])
    product = get_first_product(client)
    r = client.post(
        f"/api/v1/carts/{cart['id']}/items",
        json={"product_id": product["id"], "qty": 99999},
    )
    assert r.status_code in (409, 422)


def test_update_item_qty(client):
    customer = make_customer(client)
    cart = make_cart(client, customer["id"])
    product = get_first_product(client)
    add_item(client, cart["id"], product["id"], qty=1)
    r = client.patch(
        f"/api/v1/carts/{cart['id']}/items/{product['id']}",
        json={"qty": 3},
    )
    assert r.status_code == 200
    assert r.json()["items"][0]["qty"] == 3


def test_remove_item_from_cart(client):
    customer = make_customer(client)
    cart = make_cart(client, customer["id"])
    product = get_first_product(client)
    add_item(client, cart["id"], product["id"], qty=1)
    r = client.delete(f"/api/v1/carts/{cart['id']}/items/{product['id']}")
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_add_same_product_twice_merges_qty(client):
    customer = make_customer(client)
    cart = make_cart(client, customer["id"])
    product = get_first_product(client)
    add_item(client, cart["id"], product["id"], qty=1)
    r = client.post(
        f"/api/v1/carts/{cart['id']}/items",
        json={"product_id": product["id"], "qty": 2},
    )
    assert r.status_code == 201
    assert r.json()["items"][0]["qty"] == 3
