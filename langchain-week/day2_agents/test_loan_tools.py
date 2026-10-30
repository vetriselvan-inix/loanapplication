"""Direct checks of the loan tools against the live database. No model involved.

These expectations match the data in the dev database when they were written.
If the data changes, update the numbers here.
"""

import sys
from decimal import Decimal

import loan_tools
from loan_application.repositories import customer_repositories
from loan_application.services import loan_services
from loan_application.tables import Customer
from loan_tools import (
    _session,
    check_eligibility,
    compare_tenures,
    emi_calculator,
    get_customer,
    get_interest_rate,
)
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

sys.stdout.reconfigure(encoding="utf-8")


def test_get_customer_found():
    c = get_customer.invoke({"customer_id": 29})
    print("customer 29:", c)
    assert c["customer_id"] == 29
    assert c["age"] == 22
    assert c["monthly_income"] == 50000
    assert c["approved_loans"] == 0
    assert c["credit_score"] == 710
    assert "email" not in c and "phone" not in c and "date_of_birth" not in c


def test_get_customer_explains_the_credit_score():
    c = get_customer.invoke({"customer_id": 29})
    b = c["credit_score_breakdown"]
    print("breakdown 29:", b)
    assert (b["base"], b["income_points"], b["emi_points"], b["age_points"]) == (300, 100.0, 250.0, 60.0)
    assert b["minimum_required"] == 600
    assert b["base"] + b["income_points"] + b["emi_points"] + b["age_points"] == c["credit_score"]


def test_get_customer_with_two_approved_loans():
    c = get_customer.invoke({"customer_id": 11})
    print("customer 11:", c)
    assert c["approved_loans"] == 2


def test_get_customer_not_found_and_bad_id():
    not_found = get_customer.invoke({"customer_id": 999})
    bad = get_customer.invoke({"customer_id": 0})
    print("customer 999:", not_found)
    print("customer 0:", bad)
    assert "not found" in not_found
    assert "positive" in bad


def test_emi_calculator_matches_app():
    # Same numbers as the app's own test_calculate_emi: 3,00,000 at 12% for 36 months
    out = emi_calculator.invoke(
        {"principal": 300000, "annual_rate_percent": 12, "months": 36}
    )
    print("emi 3,00,000 / 12% / 36:", out)
    assert out["emi"] == 9964.29
    assert out["total_payment"] == round(9964.29 * 36, 2)
    assert out["total_interest"] == round(9964.29 * 36 - 300000, 2)


def test_emi_calculator_decimal_rate():
    out = emi_calculator.invoke(
        {"principal": 300000, "annual_rate_percent": 10.5, "months": 24}
    )
    print("emi 3,00,000 / 10.5% / 24:", out)
    assert 13900 < out["emi"] < 14000


def test_emi_calculator_bad_input():
    cases = [
        ({"principal": 0, "annual_rate_percent": 12, "months": 36}, "amount"),
        ({"principal": -1000, "annual_rate_percent": 12, "months": 36}, "amount"),
        ({"principal": 300000, "annual_rate_percent": 0, "months": 36}, "rate"),
        ({"principal": 300000, "annual_rate_percent": 500, "months": 36}, "rate"),
        ({"principal": 300000, "annual_rate_percent": 12, "months": 0}, "Tenure"),
        ({"principal": 300000, "annual_rate_percent": 12, "months": -6}, "Tenure"),
    ]
    for args, word in cases:
        out = emi_calculator.invoke(args)
        print(args, "->", out)
        assert isinstance(out, str) and word in out


def test_check_eligibility_eligible():
    out = check_eligibility.invoke({"customer_id": 29, "amount": 500000})
    print("eligibility 29 / 5,00,000:", out)
    assert out["eligible"] is True
    assert out["failed_rules"] == []
    assert out["max_amount_by_income"] == 1000000


def test_check_eligibility_lists_all_failures():
    # Customer 11 has 2 approved loans and income 36,000 (limit 7,20,000)
    out = check_eligibility.invoke({"customer_id": 11, "amount": 900000})
    print("eligibility 11 / 9,00,000:", out)
    assert out["eligible"] is False
    assert out["failed_rules"] == [
        "Requested amount exceeds 20x monthly income",
        "Customer already has 2 active loans",
    ]


def test_check_eligibility_low_credit_score():
    # Customer 23 has 2 approved loans and an EMI of about 88,795 on an income of
    # 50,000, so the score is 460 and two rules fail
    out = check_eligibility.invoke({"customer_id": 23, "amount": 100000})
    print("eligibility 23 / 1,00,000:", out)
    assert out["eligible"] is False
    assert out["credit_score"] == 460
    assert out["failed_rules"] == [
        "Customer already has 2 active loans",
        "Credit score must be at least 600",
    ]


def test_check_eligibility_bad_input():
    assert "not found" in check_eligibility.invoke({"customer_id": 999, "amount": 100000})
    assert "positive" in check_eligibility.invoke({"customer_id": 0, "amount": 100000})
    assert "greater than zero" in check_eligibility.invoke(
        {"customer_id": 29, "amount": -5}
    )


def test_check_eligibility_agrees_with_app():
    """For every real customer, our first failed rule must equal the app's single reason."""
    with _session() as db:
        ids = [row[0] for row in db.execute(select(Customer.id)).all()]
        assert ids, "no customers in the database"
        for cid in ids:
            customer = customer_repositories.get_by_id(db, cid)
            for amount in (10000, 500000, 5000000):
                app_reason = loan_services.check_eligibility(db, customer, Decimal(amount)) # pyright: ignore[reportArgumentType]
                ours = check_eligibility.invoke({"customer_id": cid, "amount": amount})
                expected = [app_reason] if app_reason else []
                assert ours["failed_rules"][:1] == expected, (cid, amount, ours, app_reason)
                assert ours["eligible"] == (app_reason is None)
    print(f"agrees with the app for {len(ids)} customers x 3 amounts")


def test_database_down_gives_a_message_not_a_crash():
    def unreachable():
        raise OperationalError("SELECT 1", {}, Exception("connection timeout expired"))

    real = loan_tools._session
    loan_tools._session = unreachable
    try:
        a = get_customer.invoke({"customer_id": 29})
        b = check_eligibility.invoke({"customer_id": 29, "amount": 500000})
    finally:
        loan_tools._session = real
    print("get_customer:", a)
    print("check_eligibility:", b)
    assert a == b == loan_tools.DATABASE_DOWN


def test_compare_tenures_matches_the_app():
    out = compare_tenures.invoke({"amount": 300000, "monthly_income": 50000})
    rows = {r["tenure_months"]: r for r in out["options"]}
    assert list(rows) == [12, 24, 36, 48, 60]
    # 3,00,000 at 12% for 36 months is the app's own test figure
    assert rows[36]["annual_rate_percent"] == 12
    assert rows[36]["emi"] == 9964.29
    assert rows[36]["emi_percent_of_income"] == 19.9
    # a longer tenure means a smaller EMI but more interest paid in all
    emis = [rows[m]["emi"] for m in rows]
    interest = [rows[m]["total_interest"] for m in rows]
    assert emis == sorted(emis, reverse=True)
    assert interest == sorted(interest)


def test_compare_tenures_without_income_has_no_percent():
    out = compare_tenures.invoke({"amount": 300000})
    assert all("emi_percent_of_income" not in r for r in out["options"])


def test_compare_tenures_bad_input_gives_a_message():
    assert "between Rs 10,000" in compare_tenures.invoke({"amount": 5000})
    assert "between Rs 10,000" in compare_tenures.invoke({"amount": 6_000_000})
    assert "greater than zero" in compare_tenures.invoke({"amount": 300000, "monthly_income": 0})


def test_get_interest_rate_valid_tenures():
    for tenure, rate in {12: 10, 24: 11, 36: 12, 48: 13, 60: 13}.items():
        out = get_interest_rate.invoke({"tenure_months": tenure})
        print(f"tenure {tenure}:", out)
        assert out == f"{rate}% per year for {tenure} months."


def test_get_interest_rate_invalid_tenure():
    for tenure in (30, 0, -5):
        out = get_interest_rate.invoke({"tenure_months": tenure})
        print(f"tenure {tenure}:", out)
        assert "12, 24, 36, 48 or 60" in out


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name, "\n")
