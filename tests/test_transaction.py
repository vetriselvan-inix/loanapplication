from datetime import date
from decimal import Decimal

import pytest
from helpers import make_user
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from loan_application.exceptions import ConflictError
from loan_application.schemas.auth_schemas import RegisterIn
from loan_application.services import auth_services
from loan_application.services.transaction import transaction
from loan_application.tables import Customer, User


def register_data(**overrides):
    data = {
        "username": "priya_k",
        "password": "StrongPass123",
        "name": "Priya",
        "email": "priya@example.com",
        "phone": "9876543210",
        "date_of_birth": date(1995, 4, 12),
        "monthly_income": Decimal("60000.00"),
    }
    data.update(overrides)
    return RegisterIn(**data)


def count(db, model):
    return db.scalar(select(func.count()).select_from(model))


# ---------- the transaction helper ----------
def test_transaction_commits_on_success(db_session):
    with transaction(db_session):
        make_customer_row(db_session)
    db_session.rollback()  # nothing pending is left to undo
    assert count(db_session, Customer) == 1


def test_transaction_rolls_back_integrity_error_as_conflict(db_session):
    with pytest.raises(ConflictError, match="duplicate"), transaction(db_session, "duplicate"):
        make_customer_row(db_session)
        raise IntegrityError("INSERT", {}, Exception("unique"))
    assert count(db_session, Customer) == 0


def test_transaction_rolls_back_and_reraises_other_errors(db_session):
    with pytest.raises(RuntimeError), transaction(db_session):
        make_customer_row(db_session)
        raise RuntimeError("boom")
    assert count(db_session, Customer) == 0


# ---------- registration is one unit of work ----------
def test_register_saves_customer_and_user_together(db_session):
    user, customer_id = auth_services.register_user(db_session, register_data())
    assert count(db_session, Customer) == 1
    assert count(db_session, User) == 1
    assert user.customer_id == customer_id


def test_register_user_insert_failure_leaves_no_orphan_customer(db_session, monkeypatch):
    # Simulate two requests racing for the same username: the pre-check passes,
    # then the users.username unique constraint fails on commit.
    make_user(db_session, username="priya_k")
    customers_before = count(db_session, Customer)
    monkeypatch.setattr(auth_services.user_repositories, "get_by_username", lambda db, u: None)

    with pytest.raises(ConflictError):
        auth_services.register_user(db_session, register_data())

    assert count(db_session, Customer) == customers_before
    assert db_session.scalar(select(Customer).where(Customer.email == "priya@example.com")) is None


def broken_hash(_password):
    raise RuntimeError("hashing failed")


def test_register_unexpected_failure_rolls_back_customer(db_session, monkeypatch):
    monkeypatch.setattr(auth_services, "hash_password", broken_hash)

    with pytest.raises(RuntimeError):
        auth_services.register_user(db_session, register_data())

    assert count(db_session, Customer) == 0
    assert count(db_session, User) == 0


def test_register_can_retry_after_a_failed_attempt(db_session, monkeypatch):
    monkeypatch.setattr(auth_services, "hash_password", broken_hash)
    with pytest.raises(RuntimeError):
        auth_services.register_user(db_session, register_data())
    monkeypatch.undo()

    # Before the fix this failed with "email already exists" (orphan customer)
    user, _ = auth_services.register_user(db_session, register_data())
    assert user.username == "priya_k"


def make_customer_row(db):
    db.add(
        Customer(
            name="Rolled Back",
            email="rollback@example.com",
            phone="9000000001",
            date_of_birth=date(1990, 1, 1),
            monthly_income=Decimal("50000.00"),
            credit_score=700,
        )
    )
    db.flush()
