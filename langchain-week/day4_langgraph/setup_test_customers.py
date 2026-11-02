"""Create the test customers the pre-screening cases need, in the real loan application.

By default it only SHOWS what it would create, with the credit score each customer should get.
Nothing is written until you add --create. It needs an OFFICER login, because only an officer
can add customers. Set LOAN_USER and LOAN_PASSWORD in your shell, or it asks (the password is
hidden). The assistant's own client cannot write, so this script has its own small login.

  uv run python day4_langgraph\\setup_test_customers.py            (show the plan)
  uv run python day4_langgraph\\setup_test_customers.py --create   (create them)

The ids go to test_customers.json. A customer already listed there is skipped, so running it
again only adds the ones that are missing and never makes duplicates. Customers are never
deleted by this script.
"""

import getpass
import json
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "day2_agents"))
from loan_application.schemas.customer_schemas import CustomerIn  # noqa: E402
from loan_application.services import credit_score, loan_services  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = os.environ.get("LOAN_API_URL", "http://localhost:8000").rstrip("/")
IDS_FILE = HERE / "test_customers.json"
LOAN_TENURE = 36  # months, for the starting loans

# key, name, date of birth, monthly income, the screening case it is for, a starting loan (or None)
# A starting loan is applied for right after the customer is created. It lowers the score,
# because it adds to the customer's existing EMI. The numbers in the order are not the ids.
CUSTOMERS = [
    ("approve", "Test Approve", date(1988, 1, 1), 85000, "approve: strong score, small burden", None),
    ("refer_amount", "Test Refer Amount", date(1997, 1, 1), 60000, "refer: amount above 10 lakh", None),
    ("reject_burden", "Test Reject Burden", date(1991, 1, 1), 40000, "reject: EMI burden over 50%", None),
    ("approve_score_650", "Test Approve Score", date(2004, 1, 1), 20000,
     "approve: score 650 passes (650 to 699 was the refer band before it moved to 550 to 599)", None),
    ("reject_score", "Test Reject Score", date(2004, 1, 1), 20000,
     "reject: score below 550 after a loan", 250000),
    ("refer_low_score", "Test Refer Low Score", date(2004, 1, 1), 20000,
     "refer: score in the 550 to 599 band after a loan", 180000),
]


def _age(born: date) -> int:
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def payload(number: int, name: str, born: date, income: int) -> dict:
    slug = name.lower().replace(" ", ".")
    return {
        "name": name,
        "email": f"{slug}@example.com",
        "phone": str(9000001000 + number),
        "date_of_birth": born.isoformat(),
        "monthly_income": str(income),
    }


def expected_score(born: date, income: int, loan: int | None) -> tuple[int, str]:
    existing = Decimal(0)
    if loan:
        existing = loan_services.calculate_emi(Decimal(loan), loan_services.INTEREST_RATES[LOAN_TENURE], LOAN_TENURE)
    score = credit_score.compute_credit_score(Decimal(income), _age(born), existing)
    band = "approve range" if score >= 600 else "refer range" if score >= 550 else "reject range"
    return score, band


def known_ids() -> dict[str, int]:
    return json.loads(IDS_FILE.read_text(encoding="utf-8")) if IDS_FILE.exists() else {}


def show_plan() -> None:
    have = known_ids()
    print(f"The application is at {BASE_URL}.\n")
    for number, (key, name, born, income, purpose, loan) in enumerate(CUSTOMERS, 1):
        CustomerIn(**payload(number, name, born, income))  # the app's own checks, before anything is sent
        score, band = expected_score(born, income, loan)
        state = f"already created as customer {have[key]}" if key in have else "would be created"
        print(f"{number}. {name}: {state}")
        print(f"   age {_age(born)}, income {income:,}, expected score {score} ({band})")
        if loan and key not in have:
            print(f"   starting loan: {loan:,} over {LOAN_TENURE} months (the app should approve it)")
        print(f"   for the case: {purpose}")
    missing = [c[1] for c in CUSTOMERS if c[0] not in have]
    print(f"\nNothing has been written. {len(missing)} customer(s) are missing."
          + (" Add --create to create them." if missing else ""))


def login(client: httpx.Client) -> None:
    username = os.environ.get("LOAN_USER") or input("Officer username: ").strip()
    password = os.environ.get("LOAN_PASSWORD") or getpass.getpass("Password: ")
    response = client.post("/auth/login", data={"username": username, "password": password})
    if response.status_code != 200:
        sys.exit("Login failed. Check the username and password.")
    client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"
    me = client.get("/auth/me").json()
    if me["role"] != "OFFICER":
        sys.exit("Only an officer can add customers. Log in as an officer.")
    print(f"Logged in as {me['username']} (OFFICER)\n")


def fail(response: httpx.Response, what: str) -> None:
    sys.exit(f"Stopped: {what} failed ({response.status_code}): {response.text}")


def create() -> None:
    ids = known_ids()
    missing = [(n, c) for n, c in enumerate(CUSTOMERS, 1) if c[0] not in ids]
    if not missing:
        sys.exit("Every test customer already exists (see test_customers.json). Nothing to do.")
    with httpx.Client(base_url=BASE_URL, timeout=30) as client:
        try:
            login(client)
            for number, (key, name, born, income, _, loan) in missing:
                response = client.post("/customers/", json=payload(number, name, born, income))
                if response.status_code != 201:
                    fail(response, f"creating {name}")
                ids[key] = response.json()["id"]
                IDS_FILE.write_text(json.dumps(ids, indent=2), encoding="utf-8")  # saved as we go
                print(f"created {name} as customer {ids[key]}")
                if loan:
                    applied = client.post("/loans/apply", json={
                        "customer_id": ids[key], "amount": loan, "tenure_months": LOAN_TENURE,
                    })
                    if applied.status_code != 201 or applied.json()["status"] != "APPROVED":
                        fail(applied, f"the starting loan for {name} (it should be APPROVED)")
                    print(f"  applied: loan {applied.json()['id']} for {loan:,} is APPROVED")
            print("\nScores in the app now:")
            for key, name, born, income, _, loan in CUSTOMERS:
                shown = client.get(f"/customers/{ids[key]}/credit-score").json()
                want, band = expected_score(born, income, loan)
                mark = "OK" if shown["score"] == want else f"DIFFERENT (expected {want})"
                print(f"  customer {ids[key]} {name}: {shown['score']} ({band}) {mark}")
        except httpx.RequestError:
            sys.exit("Cannot reach the loan application. Is it running (docker compose up -d)?")
    print(f"\nids saved in {IDS_FILE.name}")


if __name__ == "__main__":
    create() if "--create" in sys.argv else show_plan()
