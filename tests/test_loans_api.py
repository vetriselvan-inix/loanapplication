from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from helpers import make_customer, make_loan


def apply(client, headers, customer_id, amount=100000, tenure=12):
    return client.post(
        "/loans/apply",
        json={"customer_id": customer_id, "amount": amount, "tenure_months": tenure},
        headers=headers,
    )


# ---------- apply: success and business rejections ----------
def test_apply_approved_loan(client, officer_headers, alice):
    r = apply(client, officer_headers, alice.id)
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "APPROVED"
    assert Decimal(str(body["emi"])) == Decimal("8791.59")


def test_customer_applies_for_themselves(client, alice, alice_headers):
    assert apply(client, alice_headers, alice.id).status_code == 201


def test_underage_customer_is_rejected_not_errored(client, officer_headers, db):
    young = make_customer(db, date_of_birth=datetime.now().astimezone().date() - timedelta(days=365 * 19))
    r = apply(client, officer_headers, young.id)
    assert r.status_code == 201
    assert r.json()["status"] == "REJECTED"
    assert r.json()["rejection_reason"] == "Age must be between 21 and 60"


def test_amount_over_20x_income_is_rejected(client, officer_headers, db):
    poor = make_customer(db, monthly_income=Decimal("10000.00"))
    r = apply(client, officer_headers, poor.id, amount=250000)
    assert r.status_code == 201
    assert r.json()["status"] == "REJECTED"
    assert "20x" in r.json()["rejection_reason"]


def test_third_loan_is_rejected(client, officer_headers, db, alice):
    make_loan(db, alice)
    make_loan(db, alice)
    r = apply(client, officer_headers, alice.id)
    assert r.status_code == 201
    assert r.json()["status"] == "REJECTED"
    assert r.json()["rejection_reason"] == "Customer already has 2 active loans"


# ---------- apply: 400 / 403 / 404 ----------
@pytest.mark.parametrize("amount", [9_999, 5_000_001])
def test_apply_amount_out_of_range_is_400(client, officer_headers, alice, amount):
    r = apply(client, officer_headers, alice.id, amount=amount)
    assert r.status_code == 400
    assert r.json()["error"] == "VALIDATION_FAILED"


def test_apply_unknown_tenure_is_400(client, officer_headers, alice):
    assert apply(client, officer_headers, alice.id, tenure=18).status_code == 400


def test_apply_missing_field_is_400(client, officer_headers):
    r = client.post("/loans/apply", json={"amount": 100000}, headers=officer_headers)
    assert r.status_code == 400


def test_apply_unknown_customer_is_404(client, officer_headers):
    assert apply(client, officer_headers, 99999).status_code == 404


def test_customer_cannot_apply_for_someone_else(client, bob, alice_headers):
    r = apply(client, alice_headers, bob.id)
    assert r.status_code == 403
    assert r.json()["error"] == "FORBIDDEN"


# ---------- get ----------
def test_officer_gets_any_loan(client, officer_headers, db, alice):
    loan = make_loan(db, alice)
    assert client.get(f"/loans/{loan.id}", headers=officer_headers).status_code == 200


def test_customer_reads_own_loan_even_when_ids_differ(client, db, alice, bob, alice_headers):
    make_loan(db, bob)          # makes the loan id differ from the customer id
    own = make_loan(db, alice)
    assert own.id != alice.id
    assert client.get(f"/loans/{own.id}", headers=alice_headers).status_code == 200


def test_customer_cannot_read_another_customers_loan(client, db, bob, alice_headers):
    theirs = make_loan(db, bob)
    assert client.get(f"/loans/{theirs.id}", headers=alice_headers).status_code == 403


def test_get_missing_loan_is_404(client, officer_headers):
    r = client.get("/loans/99999", headers=officer_headers)
    assert r.status_code == 404
    assert r.json()["error"] == "NOT_FOUND"


def test_get_loan_with_id_zero_is_400(client, officer_headers):
    assert client.get("/loans/0", headers=officer_headers).status_code == 400


# ---------- list ----------
def test_list_loans_for_customer(client, officer_headers, db, alice):
    make_loan(db, alice, status="APPROVED")
    make_loan(db, alice, status="REJECTED", interest_rate=None, emi=None,
              rejection_reason="Age must be between 21 and 60")
    r = client.get(f"/loans/?customer_id={alice.id}", headers=officer_headers)
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_list_loans_filtered_by_status(client, officer_headers, db, alice):
    make_loan(db, alice, status="APPROVED")
    make_loan(db, alice, status="REJECTED", interest_rate=None, emi=None)
    r = client.get(f"/loans/?customer_id={alice.id}&status=REJECTED", headers=officer_headers)
    assert [x["status"] for x in r.json()] == ["REJECTED"]


def test_list_loans_bad_status_is_400(client, officer_headers, alice):
    r = client.get(f"/loans/?customer_id={alice.id}&status=PENDING", headers=officer_headers)
    assert r.status_code == 400


def test_list_loans_unknown_customer_is_404(client, officer_headers):
    assert client.get("/loans/?customer_id=99999", headers=officer_headers).status_code == 404


def test_list_loans_missing_customer_id_is_400(client, officer_headers):
    assert client.get("/loans/", headers=officer_headers).status_code == 400


def test_customer_cannot_list_another_customers_loans(client, bob, alice_headers):
    assert client.get(f"/loans/?customer_id={bob.id}", headers=alice_headers).status_code == 403


# ---------- delete ----------
def test_officer_deletes_loan(client, officer_headers, db, alice):
    loan = make_loan(db, alice)
    assert client.delete(f"/loans/{loan.id}", headers=officer_headers).status_code == 200
    assert client.get(f"/loans/{loan.id}", headers=officer_headers).status_code == 404


def test_delete_missing_loan_is_404(client, officer_headers):
    assert client.delete("/loans/99999", headers=officer_headers).status_code == 404


# ---------- health ----------
def test_health(client):
    assert client.get("/health").status_code == 200