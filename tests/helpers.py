import itertools
from datetime import date
from decimal import Decimal

from loan_application.security import hash_password
from loan_application.tables import Customer, Loan, User, UserRole

PASSWORD = "Pass123!"
_HASH = hash_password(PASSWORD)
_n = itertools.count(1)

def _letters(n):
    """1 -> A, 2 -> B, ... 27 -> AA. Gives names with letters only."""
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s

def make_customer(db, **overrides):
    n = next(_n)
    data = {
        "name": f"Customer{_letters(n)}",
        "email": f"customer{n}@example.com",
        "phone": f"9{n:09d}",
        "date_of_birth": date(1990, 1, 1),
        "monthly_income": Decimal("50000.00"),
        "credit_score": 700,
    }
    data.update(overrides)
    obj = Customer(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def make_user(db, customer=None, role=UserRole.CUSTOMER, **overrides):
    n = next(_n)
    data = {
        "username": f"user{n}",
        "password_hash": _HASH,
        "role": role,
        "customer_id": customer.id if customer else None,
    }
    data.update(overrides)
    obj = User(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def make_loan(db, customer, **overrides):
    data = {
        "customer_id": customer.id,
        "amount": Decimal("100000.00"),
        "tenure_months": 12,
        "interest_rate": Decimal(10),
        "emi": Decimal("8791.59"),
        "status": "APPROVED",
    }
    data.update(overrides)
    obj = Loan(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def login_headers(client, username):
    r = client.post("/auth/login", data={"username": username, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def customer_payload(**overrides):
    n = next(_n)
    body = {
        "name": "TestCustomer",
        "email": f"new{n}@example.com",
        "phone": f"8{n:09d}",
        "date_of_birth": "1990-01-01",
        "monthly_income": "50000.00",
    }
    body.update(overrides)
    return body