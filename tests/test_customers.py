"""Customer registration and retrieval."""

from tests.conftest import make_customer


def test_create_customer_success(client):
    r = client.post("/api/v1/customers", json={"name": "Bob", "email": "bob@example.com"})
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Bob"
    assert data["email"] == "bob@example.com"
    assert "id" in data


def test_create_customer_duplicate_email_returns_409(client):
    client.post("/api/v1/customers", json={"name": "Bob", "email": "dup@example.com"})
    r = client.post("/api/v1/customers", json={"name": "Bob2", "email": "dup@example.com"})
    assert r.status_code == 409


def test_create_customer_missing_field_returns_422(client):
    r = client.post("/api/v1/customers", json={"name": "NoEmail"})
    assert r.status_code == 422


def test_get_customer_success(client):
    created = make_customer(client)
    r = client.get(f"/api/v1/customers/{created['id']}")
    assert r.status_code == 200
    assert r.json()["email"] == created["email"]


def test_get_customer_not_found_returns_404(client):
    r = client.get("/api/v1/customers/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


def test_list_customers(client):
    make_customer(client, name="Alice", email="alice@list.com")
    make_customer(client, name="Bob", email="bob@list.com")
    r = client.get("/api/v1/customers")
    assert r.status_code == 200
    assert len(r.json()) >= 2
