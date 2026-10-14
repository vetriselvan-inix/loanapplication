from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import jwt
import pytest
from fastapi import HTTPException

from loan_application.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from loan_application.services.access import ensure_can_access_customer
from loan_application.services.loan_services import (
    calculate_age,
    calculate_emi,
    risk_band,
)
from loan_application.tables import UserRole


def test_emi():
    assert calculate_emi(Decimal("100000"), Decimal("10"), 12) == Decimal("8791.59")


def test_age_before_and_on_birthday():
    assert calculate_age(date(2000, 6, 15), date(2026, 6, 14)) == 25
    assert calculate_age(date(2000, 6, 15), date(2026, 6, 15)) == 26


@pytest.mark.parametrize(
    "ratio,band",
    [("29.99", "LOW"), ("30", "MEDIUM"), ("50", "MEDIUM"), ("50.01", "HIGH")],
)
def test_risk_band_boundaries(ratio, band):
    assert risk_band(Decimal(ratio)) == band


def test_password_hash_and_verify():
    h = hash_password("abc")
    assert h != "abc"
    assert verify_password("abc", h)
    assert not verify_password("wrong", h)


def test_same_password_gives_different_hashes():
    assert hash_password("abc") != hash_password("abc")


def test_token_round_trip():
    payload = decode_access_token(create_access_token(7, "OFFICER"))
    assert payload["sub"] == "7"
    assert payload["role"] == "OFFICER"


def test_tampered_token_is_rejected():
    token = create_access_token(7, "CUSTOMER")
    head, body, sig = token.split(".")
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(f"{head}.{body}x.{sig}")


def test_access_officer_sees_everything():
    ensure_can_access_customer(SimpleNamespace(role=UserRole.OFFICER, customer_id=None), 5)


def test_access_customer_own_ok_other_forbidden():
    user = SimpleNamespace(role=UserRole.CUSTOMER, customer_id=4)
    ensure_can_access_customer(user, 4)
    with pytest.raises(HTTPException) as err:
        ensure_can_access_customer(user, 5)
    assert err.value.status_code == 403