from datetime import date
from decimal import Decimal

import pytest
from helpers import customer_payload, make_customer, make_loan

from loan_application.exceptions import InvalidInputError
from loan_application.schemas.customer_schemas import CustomerIn
from loan_application.schemas.loan_schemas import LoanApplyIn
from loan_application.services import customer_services, loan_services
from loan_application.services.credit_score import compute_credit_score


def test_score_for_young_customer_with_no_loans():
    # 300 base + 100 income (50,000) + 250 no EMI + 60 age 22
    assert compute_credit_score(Decimal(50000), 22, Decimal(0)) == 710


def test_score_best_case_is_capped_at_850():
    # 300 + 200 + 250 + 100 = 850
    assert compute_credit_score(Decimal(100000), 30, Decimal(0)) == 850
    assert compute_credit_score(Decimal(500000), 30, Decimal(0)) == 850


def test_income_points_scale_below_the_cap():
    # 25,000 income gives 50 points: 300 + 50 + 250 + 100
    assert compute_credit_score(Decimal(25000), 30, Decimal(0)) == 700


def test_emi_burden_lowers_the_score():
    # EMI is half of income: 125 of 250 points. 300 + 100 + 125 + 100
    assert compute_credit_score(Decimal(50000), 30, Decimal(25000)) == 625


def test_emi_above_income_gives_zero_emi_points():
    # 88,795 EMI on 50,000 income (customer 23): 300 + 100 + 0 + 100
    assert compute_credit_score(Decimal(50000), 30, Decimal(88795)) == 500


def test_age_bands():
    base = compute_credit_score(Decimal(50000), 30, Decimal(0))
    assert base == 750
    assert compute_credit_score(Decimal(50000), 25, Decimal(0)) == 750
    assert compute_credit_score(Decimal(50000), 55, Decimal(0)) == 750
    assert compute_credit_score(Decimal(50000), 24, Decimal(0)) == 710
    assert compute_credit_score(Decimal(50000), 56, Decimal(0)) == 710
    assert compute_credit_score(Decimal(50000), 21, Decimal(0)) == 710
    assert compute_credit_score(Decimal(50000), 60, Decimal(0)) == 710
    assert compute_credit_score(Decimal(50000), 20, Decimal(0)) == 650
    assert compute_credit_score(Decimal(50000), 61, Decimal(0)) == 650


def test_score_never_drops_below_300():
    assert compute_credit_score(Decimal("0.01"), 5, Decimal(100)) == 300


# ---------- the score inside the services and API ----------
def _new_customer(db, income="50000.00"):
    # Born 1990, so always in the best age band: 300 + 100 + 250 + 100 = 750
    return customer_services.create_customer(
        db,
        CustomerIn(
            name="Score Test",
            email="score@example.com",
            phone="9111111111",
            date_of_birth=date(1990, 1, 1),
            monthly_income=Decimal(income),
        ),
    )


def _apply(db, customer, amount="300000", tenure=36):
    return loan_services.apply_for_loan(
        db,
        LoanApplyIn(
            customer_id=customer.id, amount=Decimal(amount), tenure_months=tenure
        ),
    )


def test_new_customer_gets_a_score(db_session):
    assert _new_customer(db_session).credit_score == 750


def test_updating_income_recalculates_the_score(db_session):
    customer = _new_customer(db_session)
    updated = customer_services.update_customer(
        db_session,
        customer.id,
        CustomerIn(
            name="Score Test",
            email="score@example.com",
            phone="9111111111",
            date_of_birth=date(1990, 1, 1),
            monthly_income=Decimal("100000.00"),
        ),
    )
    assert updated.credit_score == 850


def test_score_follows_loan_events(db_session):
    customer = _new_customer(db_session)

    loan = _apply(db_session, customer)  # EMI 9,964.29 is about 20% of income
    assert loan.status == "APPROVED"
    db_session.refresh(customer)
    assert customer.credit_score == 700

    loan_services.patch_loan(db_session, loan.id)  # rejected: EMI no longer counts
    db_session.refresh(customer)
    assert customer.credit_score == 750

    loan_services.approve_loan(db_session, loan.id)
    db_session.refresh(customer)
    assert customer.credit_score == 700

    loan_services.delete_loan(db_session, loan.id)
    db_session.refresh(customer)
    assert customer.credit_score == 750


def test_apply_rejected_for_low_credit_score(db_session):
    customer = make_customer(db_session)
    # EMI far above income: score 300 + 100 + 0 + 100 = 500
    make_loan(db_session, customer, emi=Decimal("88795.05"))

    loan = _apply(db_session, customer, amount="10000", tenure=12)

    assert loan.status == "REJECTED"
    assert loan.rejection_reason == "Credit score must be at least 600"


def test_approve_loan_refuses_low_credit_score(db_session):
    customer = make_customer(db_session)
    make_loan(db_session, customer, emi=Decimal("88795.05"))
    rejected = make_loan(db_session, customer, status="REJECTED", emi=None)

    with pytest.raises(InvalidInputError, match="Credit score must be at least 600"):
        loan_services.approve_loan(db_session, rejected.id)


def test_api_returns_score_and_ignores_a_score_sent_by_the_client(
    client, officer_headers
):
    body = customer_payload(credit_score=850)
    r = client.post("/customers/", json=body, headers=officer_headers)

    assert r.status_code == 201, r.text
    assert r.json()["credit_score"] == 750  # computed, not the 850 that was sent


def test_get_customer_shows_the_current_score_not_a_stale_stored_one(
    client, db_session, officer_headers
):
    # Stored 400 is out of date; born 1990 with income 50,000 the real score is 750
    customer = make_customer(db_session, credit_score=400)

    r = client.get(f"/customers/{customer.id}", headers=officer_headers)

    assert r.status_code == 200, r.text
    assert r.json()["credit_score"] == 750
    db_session.refresh(customer)
    assert customer.credit_score == 400  # reading did not write anything
