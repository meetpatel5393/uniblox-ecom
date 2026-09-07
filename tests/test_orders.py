"""Order retrieval and listing."""

from tests.conftest import (
    add_item,
    checkout,
    get_first_product,
    make_cart,
    make_customer,
    place_n_orders,
)


def test_get_order_by_id(client):
    customer = make_customer(client)
    cart = make_cart(client, customer["id"])
    product = get_first_product(client)
    add_item(client, cart["id"], product["id"], qty=2)
    order_id = checkout(client, cart["id"]).json()["id"]

    r = client.get(f"/api/v1/orders/{order_id}")
    assert r.status_code == 200
    order = r.json()
    assert order["id"] == order_id
    assert len(order["items"]) == 1
    assert order["items"][0]["qty"] == 2


def test_get_order_not_found_returns_404(client):
    r = client.get("/api/v1/orders/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


def test_list_orders_default_pagination(client):
    place_n_orders(client, 3)
    r = client.get("/api/v1/orders")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 3
    assert len(data["orders"]) >= 3
    assert data["page"] == 1


def test_list_orders_respects_page_size(client):
    place_n_orders(client, 5)
    r = client.get("/api/v1/orders?page=1&page_size=2")
    assert r.status_code == 200
    data = r.json()
    assert len(data["orders"]) <= 2
    assert data["page_size"] == 2


def test_list_orders_pagination_total_pages(client):
    place_n_orders(client, 4)
    r = client.get("/api/v1/orders?page_size=2")
    data = r.json()
    assert data["total_pages"] >= 2


def test_list_orders_page_2(client):
    place_n_orders(client, 4)
    r1 = client.get("/api/v1/orders?page=1&page_size=2")
    r2 = client.get("/api/v1/orders?page=2&page_size=2")
    ids_p1 = {o["id"] for o in r1.json()["orders"]}
    ids_p2 = {o["id"] for o in r2.json()["orders"]}
    # No overlap between pages
    assert ids_p1.isdisjoint(ids_p2)
