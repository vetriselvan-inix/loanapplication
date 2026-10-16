import pytest
from helpers import make_loan

URL = "/api/loans"


def get_page(client, headers, **params):
    return client.get(URL, params=params, headers=headers)


@pytest.fixture()
def loans(db, alice, bob):
    """25 APPROVED + 5 REJECTED loans for alice, 3 APPROVED for bob (oldest = lowest id)."""
    created = [make_loan(db, alice) for _ in range(25)]
    created += [
        make_loan(
            db, alice, status="REJECTED", rejection_reason="x", interest_rate=None, emi=None
        )
        for _ in range(5)
    ]
    created += [make_loan(db, bob) for _ in range(3)]
    return created


# ---------- metadata ----------
def test_defaults_to_first_page_of_ten(client, officer_headers, loans):
    body = get_page(client, officer_headers).json()
    assert len(body["items"]) == 10
    assert body["page"] == 1
    assert body["size"] == 10
    assert body["total"] == 33
    assert body["total_pages"] == 4
    assert body["has_next"] is True
    assert body["has_previous"] is False


def test_middle_page(client, officer_headers, loans):
    body = get_page(client, officer_headers, page=2, size=10).json()
    assert len(body["items"]) == 10
    assert body["has_next"] is True
    assert body["has_previous"] is True


def test_last_page_is_partial(client, officer_headers, loans):
    body = get_page(client, officer_headers, page=4, size=10).json()
    assert len(body["items"]) == 3  # 33 loans: 10 + 10 + 10 + 3
    assert body["has_next"] is False
    assert body["has_previous"] is True


def test_page_past_the_end_is_empty_not_an_error(client, officer_headers, loans):
    r = get_page(client, officer_headers, page=99)
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert body["total"] == 33
    assert body["has_next"] is False


def test_no_loans_at_all(client, officer_headers):
    body = get_page(client, officer_headers).json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["total_pages"] == 0
    assert body["has_next"] is False
    assert body["has_previous"] is False


# ---------- ordering ----------
def test_pages_are_oldest_first_and_do_not_overlap(client, officer_headers, loans):
    ids = []
    for page in (1, 2, 3, 4):
        ids += [loan["id"] for loan in get_page(client, officer_headers, page=page).json()["items"]]
    assert ids == sorted(loan.id for loan in loans)


# ---------- status filter ----------
def test_filter_by_status(client, officer_headers, loans):
    body = get_page(client, officer_headers, status="REJECTED").json()
    assert body["total"] == 5
    assert {loan["status"] for loan in body["items"]} == {"REJECTED"}


def test_status_filter_is_case_insensitive(client, officer_headers, loans):
    assert get_page(client, officer_headers, status="approved").json()["total"] == 28


def test_invalid_status_is_400(client, officer_headers):
    r = get_page(client, officer_headers, status="PENDING")
    assert r.status_code == 400
    assert r.json()["message"] == "Status must be APPROVED or REJECTED"


# ---------- page / size validation ----------
@pytest.mark.parametrize(
    "params",
    [{"page": 0}, {"page": -1}, {"size": 0}, {"size": 101}, {"page": "abc"}],
)
def test_invalid_page_or_size_is_400(client, officer_headers, params):
    r = get_page(client, officer_headers, **params)
    assert r.status_code == 400
    assert r.json()["error"] == "VALIDATION_FAILED"


def test_max_size_is_allowed(client, officer_headers, loans):
    body = get_page(client, officer_headers, size=100).json()
    assert len(body["items"]) == 33
    assert body["total_pages"] == 1


# ---------- who sees what ----------
def test_customer_sees_only_their_own_loans(client, alice, alice_headers, loans):
    body = get_page(client, alice_headers, size=100).json()
    assert body["total"] == 30
    assert {loan["customer_id"] for loan in body["items"]} == {alice.id}


def test_officer_sees_every_customer(client, officer_headers, alice, bob, loans):
    body = get_page(client, officer_headers, size=100).json()
    assert {loan["customer_id"] for loan in body["items"]} == {alice.id, bob.id}


def test_requires_login(client):
    assert client.get(URL).status_code == 401
