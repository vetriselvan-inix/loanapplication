import pytest
from helpers import customer_payload, make_customer, make_loan


# ---------- create ----------
def test_create_customer(client, officer_headers):
    r = client.post("/customers/", json=customer_payload(), headers=officer_headers)
    assert r.status_code == 201
    assert r.json()["name"] == "TestCustomer"


def test_create_duplicate_email_is_409(client, officer_headers, db):
    existing = make_customer(db)
    r = client.post("/customers/", json=customer_payload(email=existing.email), headers=officer_headers)
    assert r.status_code == 409
    assert r.json()["error"] == "CONFLICT"


def test_create_duplicate_phone_is_409(client, officer_headers, db):
    existing = make_customer(db)
    r = client.post("/customers/", json=customer_payload(phone=existing.phone), headers=officer_headers)
    assert r.status_code == 409


@pytest.mark.parametrize(
    "field,value",
    [("name", ""), ("email", "not-an-email"), ("phone", "123"), ("monthly_income", "-5")],
)
def test_create_invalid_body_is_400(client, officer_headers, field, value):
    r = client.post("/customers/", json=customer_payload(**{field: value}), headers=officer_headers)
    assert r.status_code == 400
    assert r.json()["error"] == "VALIDATION_FAILED"


def test_create_missing_field_is_400(client, officer_headers):
    body = customer_payload()
    del body["email"]
    assert client.post("/customers/", json=body, headers=officer_headers).status_code == 400


# ---------- get ----------
def test_officer_gets_any_customer(client, officer_headers, alice):
    r = client.get(f"/customers/{alice.id}", headers=officer_headers)
    assert r.status_code == 200
    assert r.json()["id"] == alice.id


def test_customer_gets_own_record(client, alice, alice_headers):
    assert client.get(f"/customers/{alice.id}", headers=alice_headers).status_code == 200


def test_get_missing_customer_is_404(client, officer_headers):
    r = client.get("/customers/99999", headers=officer_headers)
    assert r.status_code == 404
    assert r.json()["error"] == "NOT_FOUND"


# ---------- update ----------
def test_officer_updates_customer(client, officer_headers, alice):
    r = client.put(
        f"/customers/{alice.id}",
        json=customer_payload(email=alice.email, phone=alice.phone, name="Renamed"),
        headers=officer_headers,
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Renamed"


def test_update_missing_customer_is_404(client, officer_headers):
    r = client.put("/customers/99999", json=customer_payload(), headers=officer_headers)
    assert r.status_code == 404


def test_update_invalid_body_is_400(client, officer_headers, alice):
    r = client.put(f"/customers/{alice.id}", json=customer_payload(name=""), headers=officer_headers)
    assert r.status_code == 400


def test_update_to_taken_email_is_409(client, officer_headers, alice, bob):
    r = client.put(
        f"/customers/{bob.id}",
        json=customer_payload(email=alice.email, phone=bob.phone),
        headers=officer_headers,
    )
    assert r.status_code == 409


# ---------- delete ----------
def test_officer_deletes_customer(client, officer_headers, alice):
    assert client.delete(f"/customers/{alice.id}", headers=officer_headers).status_code == 200
    assert client.get(f"/customers/{alice.id}", headers=officer_headers).status_code == 404


def test_delete_missing_customer_is_404(client, officer_headers):
    assert client.delete("/customers/99999", headers=officer_headers).status_code == 404


def test_delete_customer_with_loans_is_409(client, officer_headers, db, alice):
    make_loan(db, alice)
    r = client.delete(f"/customers/{alice.id}", headers=officer_headers)
    assert r.status_code == 409
    assert r.json()["error"] == "CONFLICT"


# ---------- summary ----------
def test_summary_for_customer_with_one_loan(client, officer_headers, db, alice):
    make_loan(db, alice)
    r = client.get(f"/customers/{alice.id}/summary", headers=officer_headers)
    assert r.status_code == 200
    assert r.json()["approved_count"] == 1


def test_summary_missing_customer_is_404(client, officer_headers):
    assert client.get("/customers/99999/summary", headers=officer_headers).status_code == 404


def test_customer_cannot_see_another_summary(client, bob, alice_headers):
    assert client.get(f"/customers/{bob.id}/summary", headers=alice_headers).status_code == 403


# ---------- customer's loans ----------
def test_customer_loans_returns_their_loans(client, officer_headers, db, alice, bob):
    make_loan(db, bob)          # extra loan so loan ids differ from customer ids
    mine = make_loan(db, alice)
    r = client.get(f"/customers/{alice.id}/loans", headers=officer_headers)
    assert r.status_code == 200
    assert [x["id"] for x in r.json()] == [mine.id]


def test_customer_loans_accepts_lowercase_status(client, officer_headers, db, alice):
    make_loan(db, alice, status="APPROVED")
    r = client.get(f"/customers/{alice.id}/loans?status=approved", headers=officer_headers)
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_customer_loans_bad_status_is_400(client, officer_headers, alice):
    r = client.get(f"/customers/{alice.id}/loans?status=PENDING", headers=officer_headers)
    assert r.status_code == 400


def test_customer_loans_missing_customer_is_404(client, officer_headers):
    assert client.get("/customers/99999/loans", headers=officer_headers).status_code == 404


def test_customer_cannot_see_another_customers_loans(client, bob, alice_headers):
    assert client.get(f"/customers/{bob.id}/loans", headers=alice_headers).status_code == 403