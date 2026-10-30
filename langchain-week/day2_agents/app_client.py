"""Log in to the loan application and call it as that user.

The assistant never reads the database. It signs in through the app's own /auth/login,
keeps the token it gets back, and asks the app for everything else, so the app's own
rules decide what each person may see. The password is used once to log in and is not
kept; the model never sees the password or the token.

Try it:  uv run python day2_agents\\app_client.py
"""

import getpass
import os
import sys

import httpx

DEFAULT_URL = "http://localhost:8000"

CANNOT_REACH = (
    "I cannot reach the loan application right now. Please make sure it is running "
    "(docker compose up -d) and try again."
)
SESSION_EXPIRED = "Your login has expired. Please log in again."
NOT_ALLOWED = "You are not allowed to see that."


class AppError(Exception):
    """A problem the assistant can explain to the user in plain words."""


def _message(response: httpx.Response, fallback: str) -> str:
    """The app's own error message when it sent one, such as 'Customer 999 not found'."""
    try:
        body = response.json()
    except ValueError:
        return fallback
    if isinstance(body, dict) and isinstance(body.get("message"), str):
        details = body.get("details")
        if isinstance(details, list) and details:  # which field was wrong, and why
            reasons = "; ".join(
                f"{d.get('field')}: {d.get('message')}" for d in details if isinstance(d, dict)
            )
            return f"{body['message']} ({reasons})"
        return body["message"]
    return fallback


class AppSession:
    def __init__(self, base_url: str | None = None, transport=None):
        self.base_url = (base_url or os.environ.get("LOAN_API_URL", DEFAULT_URL)).rstrip("/")
        self._http = httpx.Client(base_url=self.base_url, timeout=30, transport=transport)
        self._token: str | None = None
        self.username: str | None = None
        self.role: str | None = None
        self.customer_id: int | None = None

    @property
    def logged_in(self) -> bool:
        return self._token is not None

    @property
    def is_officer(self) -> bool:
        return self.role == "OFFICER"

    def login(self, username: str, password: str) -> "AppSession":
        try:
            response = self._http.post(
                "/auth/login", data={"username": username, "password": password}
            )
        except httpx.RequestError:
            raise AppError(CANNOT_REACH) from None
        if response.status_code == 401:
            raise AppError("Wrong username or password.")
        if response.status_code != 200:
            raise AppError(f"Login failed ({response.status_code}).")
        self._token = response.json()["access_token"]
        me = self.get("/auth/me")  # who the token belongs to, and the customer id if any
        self.username, self.role, self.customer_id = me["username"], me["role"], me["customer_id"]
        return self

    def logout(self) -> None:
        self._token = None
        self.username = self.role = self.customer_id = None

    def get(self, path: str, **params):
        """GET a path of the app as the logged-in user and return the JSON."""
        if self._token is None:
            raise AppError("Please log in first.")
        try:
            response = self._http.get(
                path,
                params={k: v for k, v in params.items() if v is not None},
                headers={"Authorization": f"Bearer {self._token}"},
            )
        except httpx.RequestError:
            raise AppError(CANNOT_REACH) from None
        status = response.status_code
        if status == 401:
            self.logout()
            raise AppError(SESSION_EXPIRED)
        if status == 403:
            raise AppError(NOT_ALLOWED)
        if status == 404:
            raise AppError(_message(response, "Not found."))
        if status in (400, 422):
            raise AppError(_message(response, "That request was not valid."))
        if status >= 500:
            raise AppError("The loan application had a problem. Please try again.")
        return response.json()


def prompt_login(session: AppSession, attempts: int = 3, ask=input, ask_secret=getpass.getpass) -> bool:
    """Ask for a username and a hidden password, up to a few times. True when logged in."""
    for _ in range(attempts):
        username = ask("Username: ").strip()
        password = ask_secret("Password: ")
        try:
            session.login(username, password)
            return True
        except AppError as problem:
            print(problem)
            if str(problem) == CANNOT_REACH:
                return False  # trying again will not help
    return False


def login_from_environment(session: AppSession) -> bool:
    """For scripted runs: LOAN_USER and LOAN_PASSWORD from the environment. False if unset."""
    username, password = os.environ.get("LOAN_USER"), os.environ.get("LOAN_PASSWORD")
    if not username or not password:
        return False
    session.login(username, password)
    return True


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # the Windows console cannot print the rupee sign otherwise
    session = AppSession()
    if prompt_login(session):
        who = f"customer {session.customer_id}" if session.customer_id else "all customers"
        print(f"Logged in as {session.username} ({session.role}, {who})")
    else:
        print("Could not log in.")
