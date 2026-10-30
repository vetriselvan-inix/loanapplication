from datetime import date
from decimal import Decimal

import pytest
from helpers import customer_payload, login_headers, make_customer, make_loan, make_user

from loan_application.exceptions import InvalidInputError
from loan_application.schemas.customer_schemas import CustomerIn
from loan_application.schemas.loan_schemas import LoanApplyIn
from loan_application.services import customer_services, loan_services
from loan_application.services.credit_score import compute_credit_score, score_breakdown


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


# ---------- the score breakdown ----------
def test_breakdown_for_customer_29():
    b = score_breakdown(Decimal(50000), 22, Decimal(0))
    assert b["score"] == 710
    assert (b["base"], b["income_points"], b["emi_points"], b["age_points"]) == (
        300,
        100.0,
        250.0,
        60.0,
    )
    assert b["emi_percent_of_income"] == 0.0
    assert b["meets_minimum"] is True


def test_breakdown_for_customer_11():
    # 300 + 72 + 174.7 + 60 = 606.7, rounded to 607
    b = score_breakdown(Decimal(36000), 24, Decimal("10843.45"))
    assert b["score"] == 607
    assert (b["income_points"], b["emi_points"], b["age_points"]) == (72.0, 174.7, 60.0)
    assert b["emi_percent_of_income"] == 30.1
    assert b["meets_minimum"] is True


def test_breakdown_below_the_minimum():
    b = score_breakdown(Decimal(50000), 24, Decimal("88795.05"))
    assert b["score"] == 460
    assert b["emi_points"] == 0.0
    # the EMI is 177.6% of income: the points stop at 0, but the share shown is the real one
    assert b["emi_percent_of_income"] == 177.6
    assert b["meets_minimum"] is False
    assert b["minimum_required"] == 600


def test_breakdown_score_always_equals_compute_credit_score():
    for income, age, emi in [
        (50000, 30, 0),
        (9000, 18, 0),
        (25000, 58, 5000),
        (120000, 40, 90000),
    ]:
        b = score_breakdown(Decimal(income), age, Decimal(emi))
        assert b["score"] == compute_credit_score(Decimal(income), age, Decimal(emi))
        # the shown parts add up to the score within rounding
        parts = b["base"] + b["income_points"] + b["emi_points"] + b["age_points"]
        assert abs(parts - b["score"]) <= 0.5 or b["score"] in (300, 850)


# ---------- the breakdown endpoint ----------
def test_officer_can_read_any_customers_breakdown(client, db_session, officer_headers):
    customer = make_customer(db_session)

    r = client.get(f"/customers/{customer.id}/credit-score", headers=officer_headers)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["customer_id"] == customer.id
    assert body["score"] == 750
    assert body["income_points"] == 100.0
    assert body["emi_points"] == 250.0
    assert body["age_points"] == 100.0
    assert body["meets_minimum"] is True


def test_customer_can_read_only_their_own_breakdown(client, db_session):
    mine = make_customer(db_session)
    other = make_customer(db_session)
    headers = login_headers(client, make_user(db_session, mine).username)

    own = client.get(f"/customers/{mine.id}/credit-score", headers=headers)
    theirs = client.get(f"/customers/{other.id}/credit-score", headers=headers)

    assert own.status_code == 200, own.text
    assert theirs.status_code == 403


def test_breakdown_needs_login_and_a_real_customer(client, db_session, officer_headers):
    customer = make_customer(db_session)

    assert client.get(f"/customers/{customer.id}/credit-score").status_code == 401
    assert (
        client.get("/customers/999/credit-score", headers=officer_headers).status_code
        == 404
    )
