"""Checks of the login client. No app, database or model needed: the app is simulated."""

import sys

import httpx
from app_client import (
    CANNOT_REACH,
    NOT_ALLOWED,
    SESSION_EXPIRED,
    AppError,
    AppSession,
    login_from_environment,
    prompt_login,
)

sys.stdout.reconfigure(encoding="utf-8")

TOKEN = "token-abc"


def fake_app(users, seen=None, expire_after=None):
    """A stand-in for the loan application. users maps username to (password, role, customer_id)."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        path = request.url.path
        if path == "/auth/login":
            form = dict(pair.split("=", 1) for pair in request.content.decode().split("&"))
            entry = users.get(form["username"])
            if entry is None or entry[0] != form["password"]:
                return httpx.Response(401, json={"detail": "Invalid credentials"})
            return httpx.Response(200, json={"access_token": TOKEN, "token_type": "bearer"})
        if request.headers.get("authorization") != f"Bearer {TOKEN}":
            return httpx.Response(401, json={"detail": "Could not validate credentials"})
        calls["n"] += 1
        if expire_after is not None and calls["n"] > expire_after:
            return httpx.Response(401, json={"detail": "expired"})
        if path == "/auth/me":
            name = next(iter(users))
            _, role, customer_id = users[name]
            return httpx.Response(200, json={"username": name, "role": role, "customer_id": customer_id})
        if path == "/customers/11":
            return httpx.Response(403, json={"detail": "Not allowed"})
        if path == "/customers/999":
            return httpx.Response(404, json={"error": "NOT_FOUND", "message": "Customer 999 not found"})
        if path == "/customers/5/eligibility":
            return httpx.Response(400, json={"error": "VALIDATION_FAILED", "message": "Invalid input"})
        if path == "/boom":
            return httpx.Response(500, text="oops")
        return httpx.Response(200, json={"path": path, "query": dict(request.url.params)})

    return httpx.MockTransport(handler)


def session_for(users, **kw):
    return AppSession(base_url="http://app", transport=fake_app(users, **kw))


HYDRA = {"hydra": ("secret123", "CUSTOMER", 29)}


def test_login_remembers_who_the_user_is():
    s = session_for(HYDRA).login("hydra", "secret123")
    assert s.logged_in and not s.is_officer
    assert (s.username, s.role, s.customer_id) == ("hydra", "CUSTOMER", 29)


def test_an_officer_has_no_customer_id():
    s = session_for({"vetri": ("pw-officer", "OFFICER", None)}).login("vetri", "pw-officer")
    assert s.is_officer and s.customer_id is None


def test_wrong_password_is_refused_and_nothing_is_kept():
    s = session_for(HYDRA)
    try:
        s.login("hydra", "wrong")
        raise AssertionError("should have been refused")
    except AppError as problem:
        assert str(problem) == "Wrong username or password."
    assert not s.logged_in


def test_the_password_is_not_kept_anywhere_on_the_session():
    s = session_for(HYDRA).login("hydra", "secret123")
    assert "secret123" not in repr(vars(s))


def test_requests_carry_the_token_and_leave_out_empty_parameters():
    seen = []
    s = session_for(HYDRA, seen=seen).login("hydra", "secret123")
    out = s.get("/customers/29/eligibility", amount=500000, tenure_months=None)
    assert out["query"] == {"amount": "500000"}
    assert seen[-1].headers["authorization"] == f"Bearer {TOKEN}"


def test_app_errors_become_plain_messages():
    s = session_for(HYDRA).login("hydra", "secret123")
    expectations = {
        "/customers/11": NOT_ALLOWED,
        "/customers/999": "Customer 999 not found",
        "/customers/5/eligibility": "Invalid input",
        "/boom": "The loan application had a problem. Please try again.",
    }
    for path, expected in expectations.items():
        try:
            s.get(path)
            raise AssertionError(f"{path} should have failed")
        except AppError as problem:
            assert str(problem) == expected, (path, str(problem))


def test_an_expired_token_logs_out_and_asks_for_a_new_login():
    s = session_for(HYDRA, expire_after=1).login("hydra", "secret123")  # /auth/me is call 1
    try:
        s.get("/customers/29")
        raise AssertionError("should have expired")
    except AppError as problem:
        assert str(problem) == SESSION_EXPIRED
    assert not s.logged_in and s.role is None


def test_get_before_login_is_refused():
    try:
        session_for(HYDRA).get("/customers/29")
        raise AssertionError("should need a login")
    except AppError as problem:
        assert "log in" in str(problem)


def test_an_unreachable_app_gives_one_clear_message():
    def down(request):
        raise httpx.ConnectError("refused")

    s = AppSession(base_url="http://app", transport=httpx.MockTransport(down))
    try:
        s.login("hydra", "x")
        raise AssertionError("should not connect")
    except AppError as problem:
        assert str(problem) == CANNOT_REACH


def test_the_login_prompt_retries_then_succeeds():
    answers = iter([("hydra", "bad"), ("hydra", "secret123")])
    current = {}

    def ask(_prompt):
        current["pair"] = next(answers)
        return current["pair"][0]

    s = session_for(HYDRA)
    assert prompt_login(s, ask=ask, ask_secret=lambda _p: current["pair"][1]) is True
    assert s.customer_id == 29


def test_the_login_prompt_gives_up_after_three_wrong_tries():
    s = session_for(HYDRA)
    assert prompt_login(s, ask=lambda _p: "hydra", ask_secret=lambda _p: "nope") is False
    assert not s.logged_in


def test_scripted_login_uses_the_environment_only_when_both_are_set(monkeypatch=None):
    import os

    saved = {k: os.environ.pop(k, None) for k in ("LOAN_USER", "LOAN_PASSWORD")}
    try:
        assert login_from_environment(session_for(HYDRA)) is False
        os.environ["LOAN_USER"], os.environ["LOAN_PASSWORD"] = "hydra", "secret123"
        s = session_for(HYDRA)
        assert login_from_environment(s) is True and s.customer_id == 29
    finally:
        for key, value in saved.items():
            os.environ.pop(key, None)
            if value is not None:
                os.environ[key] = value


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
