"""Day 3 assignment, item 5: the Day 2 agent with search_policy added, on questions that need
the live data, the policy, or both. The order of tool calls is printed and saved.

The assistant now needs a login. Use an OFFICER login, because two questions are about other
customers. Set LOAN_USER and LOAN_PASSWORD in your shell first (never put them in a file).

Run:  uv run python -W ignore day3_rag\\demo_combined.py
Output is saved to day3_rag\\demo_combined_login.txt. The earlier demo_combined.txt, recorded
before the login existed, is left alone. Tracing stays off: this agent reads real customers.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "day2_agents"))
from app_client import AppSession, login_from_environment  # noqa: E402
from loan_agent import build_agent, show  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")  # the Windows console cannot print the rupee sign otherwise

QUESTIONS = [
    # needs emi_calculator + search_policy + percent_of (the guide's demo question)
    "I want 6,00,000 for 36 months at 11%. What is the EMI and the processing fee?",
    # needs the live data and the policy in one answer
    "Is customer 29 eligible for a loan of 5,00,000 for 36 months, and what documents will they need?",
    # policy only
    "How soon is the money disbursed after my documents are verified?",
    # live data only
    "Is customer 11 eligible for a loan of 1,00,000 for 12 months?",
    # the policy and the app both state a minimum score; they must agree
    "What credit score do I need to get a loan?",
]

if __name__ == "__main__":
    session = AppSession()
    if not login_from_environment(session) or not session.is_officer:
        sys.exit("Set LOAN_USER and LOAN_PASSWORD to an OFFICER login, then run this again.")
    agent = build_agent(session)
    path = Path(__file__).resolve().parent / "demo_combined_login.txt"
    with path.open("w", encoding="utf-8") as f:

        def out(line=""):
            print(line, flush=True)
            f.write(line + "\n")
            f.flush()

        for i, question in enumerate(QUESTIONS, 1):
            out(f"=== Q{i}: {question}")
            result = agent.invoke({"messages": [{"role": "user", "content": question}]})
            show(result["messages"], out)
            out(f"ANSWER: {result['messages'][-1].content}\n")
        out(f"written: {path}")
