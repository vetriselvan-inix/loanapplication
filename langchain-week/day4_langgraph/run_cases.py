"""Run the eight pre-screening cases against the real loan application and save the output.

Needs an OFFICER login (LOAN_USER and LOAN_PASSWORD in your shell), the test customers from
setup_test_customers.py (their ids are in test_customers.json), and Ollama running. Each case
makes one model call, about 20 to 40 seconds, so the run takes about 5 minutes.

Run:  uv run python -W ignore day4_langgraph\\run_cases.py
Output is saved to day4_langgraph\\test_output.txt.
"""

import json
import sys
from pathlib import Path

from prescreen_graph import build_graph, prescreen

from app_client import AppError, AppSession, login_from_environment

sys.stdout.reconfigure(encoding="utf-8")  # the Windows console cannot print the rupee sign otherwise

HERE = Path(__file__).resolve().parent
NO_SUCH_CUSTOMER = 999999

# label, which test customer (a key of test_customers.json, or a plain id), email, expected decision
CASES = [
    ("1", "approve", "Hi, this is Ramesh Kumar. I would like a loan of 5 lakh for 3 years to renovate my house.", "approve"),
    ("2", "refer_amount", "I need 12,00,000 for 60 months.", "refer"),
    ("3", "reject_burden", "I need a loan of 7 lakh for 24 months.", "reject"),
    ("4", "refer_low_score", "I need 1 lakh for 36 months.", "refer"),
    ("5", "approve", "I want a loan for a car.", "need_info"),
    ("6", NO_SUCH_CUSTOMER, "I need 3 lakh for 2 years.", "need_info"),
    ("7", "reject_score", "I need 10,000 for 5 years.", "reject"),
    ("8", "approve_score_650", "I need 2.5 lakh for 36 months.", "approve"),  # score 650: no longer a referral
]

if __name__ == "__main__":
    session = AppSession()
    try:
        logged_in = login_from_environment(session)
    except AppError as problem:
        sys.exit(str(problem))
    if not logged_in or not session.is_officer:
        sys.exit("Set LOAN_USER and LOAN_PASSWORD to an OFFICER login, then run this again.")
    ids_file = HERE / "test_customers.json"
    if not ids_file.exists():
        sys.exit("test_customers.json is missing. Run setup_test_customers.py --create first.")
    ids = json.loads(ids_file.read_text(encoding="utf-8"))
    graph = build_graph(session)
    path = HERE / "test_output.txt"
    mismatches = []
    with path.open("w", encoding="utf-8") as f:

        def out(line=""):
            print(line, flush=True)
            f.write(line + "\n")
            f.flush()

        for label, who, email, expected in CASES:
            customer_id = ids[who] if isinstance(who, str) else who
            out(f"=== Case {label}: customer {customer_id}")
            out(f"email:    {email}")
            result = prescreen(graph, email, customer_id)
            decision = result.get("decision")
            verdict = "OK" if decision == expected else f"WRONG, expected {expected}"
            out(f"decision: {decision} ({verdict})")
            out(f"reason:   {result.get('reason')}")
            out(f"log:      {' -> '.join(result['log'])}\n")
            if decision != expected:
                mismatches.append(label)
        summary = f"ALL {len(CASES)} DECISIONS MATCH" if not mismatches else f"MISMATCH in cases {', '.join(mismatches)}"
        out(summary)
    sys.exit(1 if mismatches else 0)
