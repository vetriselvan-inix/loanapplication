from datetime import datetime, timedelta, timezone

import jwt
import pytest

from helpers import PASSWORD, customer_payload, make_loan, make_user
from loan_application.config import settings
from loan_application.tables import UserRole


def make_token(sub, minutes=30, key=None):
    now = datetime.now(timezone.utc)
    payload = {"sub": str(sub), "role": "OFFICER", "iat": now,
               "exp": now + timedelta(minutes=minutes)}
    return jwt.encode(payload, key or settings.jwt_secret_key,
                      algorithm=settings.jwt_algorithm)


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


# ---- login ----
def test_login_returns_token(client, officer):
    r = client.post("/auth/login", data={"username": officer.username, "password": PASSWORD})
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_login_wrong_password_is_401(client, officer):
    r = client.post("/auth/login", data={"username": officer.username, "password": "wrong"})
    assert r.status_code == 401
    assert r.json()["error"] == "UNAUTHORIZED"


def test_login_unknown_user_is_401(client):
    r = client.post("/auth/login", data={"username": "nobody", "password": "x"})
    assert r.status_code == 401


def test_login_inactive_user_is_401(client, db):
    user = make_user(db, role=UserRole.OFFICER, is_active=False)
    r = client.post("/auth/login", data={"username": user.username, "password": PASSWORD})
    assert r.status_code == 401


def test_login_missing_fields_is_400(client):
    r = client.post("/auth/login", data={})
    assert r.status_code == 400


# ---- 401: every protected route needs a token ----
PROTECTED = [
    ("POST", "/loans/apply"),
    ("GET", "/loans/1"),
    ("GET", "/loans/?customer_id=1"),
    ("DELETE", "/loans/1"),
    ("POST", "/customers/"),
    ("GET", "/customers/1"),
    ("PUT", "/customers/1"),
    ("DELETE", "/customers/1"),
    ("GET", "/customers/1/summary"),
    ("GET", "/customers/1/loans"),
]


@pytest.mark.parametrize("method,path", PROTECTED)
def test_route_without_token_is_401(client, method, path):
    assert client.request(method, path).status_code == 401


def test_garbage_token_is_401(client):
    assert client.get("/customers/1", headers=bearer("abc.def.ghi")).status_code == 401


def test_expired_token_is_401(client, officer):
    r = client.get("/customers/1", headers=bearer(make_token(officer.id, minutes=-1)))
    assert r.status_code == 401


def test_token_with_wrong_key_is_401(client, officer):
    r = client.get("/customers/1", headers=bearer(make_token(officer.id, key="x" * 40)))
    assert r.status_code == 401


# ---- 403: logged in but not allowed ----
def test_customer_cannot_create_customer(client, alice_headers):
    r = client.post("/customers/", json=customer_payload(), headers=alice_headers)
    assert r.status_code == 403
    assert r.json()["error"] == "FORBIDDEN"


def test_customer_cannot_delete_customer(client, alice_headers, bob):
    assert client.delete(f"/customers/{bob.id}", headers=alice_headers).status_code == 403


def test_customer_cannot_delete_loan(client, db, alice, alice_headers):
    loan = make_loan(db, alice)
    assert client.delete(f"/loans/{loan.id}", headers=alice_headers).status_code == 403


def test_customer_cannot_read_other_customer(client, bob, alice_headers):
    assert client.get(f"/customers/{bob.id}", headers=alice_headers).status_code == 403


def test_customer_cannot_read_other_customers_loan(client, db, bob, alice_headers):
    loan = make_loan(db, bob)
    assert client.get(f"/loans/{loan.id}", headers=alice_headers).status_code == 403


# ---- registration ----
def register_body(**overrides):
    body = {
        "username": "priya_k",
        "password": "StrongPass123",
        "name": "Priya",
        "email": "priya@example.com",
        "phone": "9876543210",
        "date_of_birth": "1995-04-12",
        "monthly_income": "60000.00",
    }
    body.update(overrides)
    return body


def login_token(client, username="priya_k", password="StrongPass123"):
    r = client.post("/auth/login", data={"username": username, "password": password})
    return r.json()["access_token"]


def test_register_creates_customer_and_login(client):
    r = client.post("/auth/register", json=register_body())
    assert r.status_code == 201
    assert r.json()["username"] == "priya_k"


def test_registered_user_reads_own_record_only(client, bob):
    customer_id = client.post("/auth/register", json=register_body()).json()["customer_id"]
    headers = bearer(login_token(client))
    assert client.get(f"/customers/{customer_id}", headers=headers).status_code == 200
    assert client.get(f"/customers/{bob.id}", headers=headers).status_code == 403


def test_registered_user_cannot_create_customers(client):
    client.post("/auth/register", json=register_body())
    r = client.post("/customers/", json=customer_payload(), headers=bearer(login_token(client)))
    assert r.status_code == 403


def test_register_ignores_a_role_in_the_body(client):
    client.post("/auth/register", json=register_body(role="OFFICER"))
    r = client.post("/customers/", json=customer_payload(), headers=bearer(login_token(client)))
    assert r.status_code == 403  # still a customer, so the role field did nothing


def test_register_duplicate_username_is_409(client):
    client.post("/auth/register", json=register_body())
    r = client.post("/auth/register", json=register_body(email="other@example.com", phone="9111111111"))
    assert r.status_code == 409


def test_register_duplicate_email_is_409(client):
    client.post("/auth/register", json=register_body())
    r = client.post("/auth/register", json=register_body(username="other_user", phone="9111111111"))
    assert r.status_code == 409 


def test_register_short_password_is_400(client):
    assert client.post("/auth/register", json=register_body(password="short")).status_code == 400


def test_register_bad_username_is_400(client):
    assert client.post("/auth/register", json=register_body(username="bad name!")).status_code == 400