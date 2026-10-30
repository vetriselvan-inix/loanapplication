from datetime import date, datetime
from decimal import Decimal

from helpers import login_headers, make_customer, make_loan, make_user

from loan_application.services import credit_score, eligibility_advice, loan_services
from loan_application.services.credit_score import compute_credit_score
from loan_application.services.eligibility_advice import rupees


def today():
    return datetime.now().astimezone().date()


def age_of(customer):
    return loan_services.calculate_age(customer.date_of_birth, today())


def report(db, customer, amount, tenure=None):
    return eligibility_advice.eligibility_report(db, customer, Decimal(amount), tenure)


def advice_for(result, rule):
    return next(a for a in result["advice"] if a["rule"] == rule)


def aged(years):
    """A birth date that makes someone exactly `years` old today, whatever today is."""
    t = today()
    try:
        return t.replace(year=t.year - years)
    except ValueError:  # 29 February
        return date(t.year - years, 2, 28)


# ---------- the rupee format ----------
def test_rupees_uses_indian_grouping():
    assert rupees(Decimal(500)) == "Rs 500"
    assert rupees(Decimal(50000)) == "Rs 50,000"
    assert rupees(Decimal(1000000)) == "Rs 10,00,000"
    assert rupees(Decimal(5000000)) == "Rs 50,00,000"
    assert rupees(Decimal("30100.7")) == "Rs 30,100"


# ---------- one list of rules ----------
def test_check_eligibility_is_the_first_of_failed_rules(db_session):
    scenarios = [
        make_customer(db_session),  # fine
        make_customer(db_session, date_of_birth=aged(19)),  # too young
        make_customer(db_session, monthly_income=Decimal(9000)),  # low income
    ]
    for customer in scenarios:
        for amount in (10000, 500000, 5000000):
            failed = loan_services.failed_rules(db_session, customer, Decimal(amount))
            first = loan_services.check_eligibility(
                db_session, customer, Decimal(amount)
            )
            assert first == (failed[0] if failed else None)


def test_every_failed_rule_is_listed_in_order(db_session):
    # 19 years old, income 9,000, asking 5,00,000: age, income limit and score all fail
    customer = make_customer(
        db_session, date_of_birth=aged(19), monthly_income=Decimal(9000)
    )

    failed = loan_services.failed_rules(db_session, customer, Decimal(500000))

    assert failed == [
        loan_services.AGE_REASON,
        loan_services.INCOME_REASON,
        loan_services.SCORE_REASON,
    ]


# ---------- the EMI limit behind the score rule ----------
def test_max_emi_is_the_exact_edge_of_the_minimum_score():
    for income, age in [(50000, 30), (36000, 24), (25000, 40), (10000, 58)]:
        limit = credit_score.max_emi_for_minimum(Decimal(income), age)
        assert compute_credit_score(Decimal(income), age, limit) >= 600
        assert compute_credit_score(Decimal(income), age, limit + 1) < 600


def test_max_emi_is_none_when_even_no_emi_cannot_reach_the_minimum():
    # age gives 0 points and 9,000 income gives 18, so the best possible score is 568
    assert credit_score.max_emi_for_minimum(Decimal(9000), 18) is None


# ---------- the report ----------
def test_an_eligible_request_has_no_failures_and_a_projection(db_session):
    customer = make_customer(db_session)

    result = report(db_session, customer, 500000, 36)

    assert result["eligible"] is True
    assert result["failed_rules"] == []
    assert result["max_amount_by_income"] == 1000000.0
    new_emi = loan_services.calculate_emi(Decimal(500000), Decimal(12), 36)
    expected = compute_credit_score(Decimal(50000), age_of(customer), new_emi)
    assert result["projection"]["new_emi"] == float(new_emi)
    assert result["projection"]["score_after_loan"] == expected
    assert result["projection"]["stays_above_minimum"] is True
    assert result["advice"] == []


def test_amount_above_the_income_limit_says_how_much_is_allowed(db_session):
    customer = make_customer(db_session)  # income 50,000 gives a limit of 10,00,000

    result = report(db_session, customer, 1500000)

    assert result["failed_rules"] == [loan_services.INCOME_REASON]
    item = advice_for(result, loan_services.INCOME_REASON)
    assert item["fixable"] is True
    assert "Rs 10,00,000" in item["suggestion"]


def test_age_and_two_loans_are_not_fixable_by_changing_the_request(db_session):
    young = make_customer(db_session, date_of_birth=aged(19))
    busy = make_customer(db_session)
    make_loan(db_session, busy, emi=Decimal(1000))
    make_loan(db_session, busy, emi=Decimal(1000))

    young_result = report(db_session, young, 100000)
    busy_result = report(db_session, busy, 100000)

    assert advice_for(young_result, loan_services.AGE_REASON)["fixable"] is False
    assert "19" in advice_for(young_result, loan_services.AGE_REASON)["suggestion"]
    assert busy_result["failed_rules"] == [loan_services.LOANS_REASON]
    assert advice_for(busy_result, loan_services.LOANS_REASON)["fixable"] is False


def test_low_score_from_heavy_emi_says_how_far_the_emi_must_fall(db_session):
    customer = make_customer(db_session)
    make_loan(db_session, customer, emi=Decimal("88795.05"))

    result = report(db_session, customer, 100000)

    assert result["failed_rules"] == [loan_services.SCORE_REASON]
    assert result["credit_score"] < 600
    item = advice_for(result, loan_services.SCORE_REASON)
    assert item["fixable"] is True
    limit = credit_score.max_emi_for_minimum(Decimal(50000), age_of(customer))
    assert rupees(limit) in item["suggestion"]
    assert "Rs 88,795" in item["suggestion"]


def test_low_score_that_no_emi_change_can_fix_says_income_is_needed(db_session):
    customer = make_customer(
        db_session, date_of_birth=aged(19), monthly_income=Decimal(9000)
    )

    result = report(db_session, customer, 50000)

    item = advice_for(result, loan_services.SCORE_REASON)
    assert item["fixable"] is False
    assert "higher income" in item["suggestion"]


def test_a_loan_that_would_sink_the_next_application_is_flagged(db_session):
    customer = make_customer(db_session)
    make_loan(db_session, customer, emi=Decimal(17000))  # score is still above 600

    # a 12 month loan of 5,00,000 has an EMI near 44,000 on an income of 50,000
    result = report(db_session, customer, 500000, 12)

    assert result["eligible"] is True
    assert result["projection"]["stays_above_minimum"] is False
    item = advice_for(result, "After this loan")
    assert "further application would be refused" in item["suggestion"]


def test_the_projection_is_left_out_without_a_tenure(db_session):
    customer = make_customer(db_session)

    assert report(db_session, customer, 500000)["projection"] is None


# ---------- the endpoint ----------
def test_officer_can_check_any_customers_eligibility(
    client, db_session, officer_headers
):
    customer = make_customer(db_session)

    r = client.get(
        f"/customers/{customer.id}/eligibility",
        params={"amount": 1500000, "tenure_months": 36},
        headers=officer_headers,
    )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["eligible"] is False
    assert body["failed_rules"] == [loan_services.INCOME_REASON]
    assert body["projection"]["tenure_months"] == 36
    assert body["advice"][0]["fixable"] is True


def test_customer_can_check_only_their_own_eligibility(client, db_session):
    mine = make_customer(db_session)
    other = make_customer(db_session)
    headers = login_headers(client, make_user(db_session, mine).username)

    own = client.get(
        f"/customers/{mine.id}/eligibility", params={"amount": 100000}, headers=headers
    )
    theirs = client.get(
        f"/customers/{other.id}/eligibility", params={"amount": 100000}, headers=headers
    )

    assert own.status_code == 200, own.text
    assert theirs.status_code == 403


def test_eligibility_check_is_read_only(client, db_session, officer_headers):
    customer = make_customer(db_session)

    client.get(
        f"/customers/{customer.id}/eligibility",
        params={"amount": 100000, "tenure_months": 12},
        headers=officer_headers,
    )

    assert loan_services.list_loans_for_customer(db_session, customer.id) == []


def test_eligibility_rejects_bad_input_and_unknown_customers(
    client, db_session, officer_headers
):
    customer = make_customer(db_session)
    url = f"/customers/{customer.id}/eligibility"

    assert client.get(url, params={"amount": 100000}).status_code == 401
    assert client.get(url, headers=officer_headers).status_code == 400  # no amount
    assert (
        client.get(url, params={"amount": 5000}, headers=officer_headers).status_code
        == 400
    )
    assert (
        client.get(
            url, params={"amount": 100000, "tenure_months": 30}, headers=officer_headers
        ).status_code
        == 400
    )
    assert (
        client.get(
            "/customers/999/eligibility",
            params={"amount": 100000},
            headers=officer_headers,
        ).status_code
        == 404
    )
