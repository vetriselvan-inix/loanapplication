"""Day 3 assignment: run the ten policy questions and write answers.md.

Run:  uv run python -W ignore day3_rag\\run_questions.py
Takes about 4 minutes (one model call per question, about 20 seconds each on CPU).
"""

import sys
from pathlib import Path

from ask_policy import NOT_FOUND, ask_policy
from policy_rag import build_index

sys.stdout.reconfigure(encoding="utf-8")  # the Windows console cannot print the rupee sign otherwise

# (question, what a good answer contains, section it should cite, words that must appear)
# Expected answers follow our hybrid policy (data/loan_policy.txt), not the guide's original,
# for the questions where the two differ (2 and 10).
QUESTIONS = [
    ("What is the minimum age?", "21 (section 1.1)", "1.1", ["21"]),
    ("What happens if my credit score is 680?",
     "680 is above the minimum of 600, so the score rule is met (1.3)", "1.3", ["600"]),
    ("What is the processing fee on a 6,00,000 loan?",
     "1.5 percent plus taxes, so 9,000 plus taxes (3.2); ask_policy does no sums, so the rate is enough",
     "3.2", ["1.5"]),
    ("Can I prepay after 8 months?",
     "Yes. A 2 percent charge applies within 12 months (3.3)", "3.3", ["2 percent", "12 months"]),
    ("What income proof does a self-employed applicant need?", "Last 2 years of ITR (4.3)", "4.3", ["ITR"]),
    ("Who approves a 12,00,000 loan?", "A senior manager (2.3)", "2.3", ["senior manager"]),
    ("How long until disbursal?", "3 working days after verification (5.1)", "5.1", ["3 working days"]),
    ("Can the money go to my friend's account?",
     "No, only the applicant's own account (5.2)", "5.2", ["own"]),
    ("What is the policy on gold loans?", "Not in the policy. Must say it could not find it.", None, []),
    ("What interest rate will I get with a 750 score?",
     "The rate depends on the tenure (10 to 13 percent), not the score (3.1). Must not invent a rate.",
     "3.1", ["tenure"]),
]


def check(section, words, result) -> str:
    """A keyword check, not a judge: PASS only if the expected section and words are there."""
    answer = result["answer"]
    if section is None:  # the unanswerable question
        return "PASS" if answer == NOT_FOUND and not result["sections"] else "CHECK"
    if section not in result["sections"]:
        return "CHECK"
    return "PASS" if all(w.lower() in answer.lower() for w in words) else "CHECK"


def run(store, label=""):
    rows = []
    for i, (question, expected, section, words) in enumerate(QUESTIONS, 1):
        result = ask_policy(question, store=store)
        verdict = check(section, words, result)
        print(f"{label}Q{i} {verdict}: {question}\n    {result['answer']}  {result['sections']}", flush=True)
        rows.append((i, question, result, expected, verdict))
    return rows


def write_markdown(rows, path, title, note=""):
    lines = [f"# {title}", ""]
    if note:
        lines += [note, ""]
    passed = sum(1 for r in rows if r[4] == "PASS")
    lines += [f"Automatic keyword check: {passed} of {len(rows)} PASS. "
              "CHECK means read the answer yourself; it does not always mean wrong.", ""]
    for i, question, result, expected, verdict in rows:
        sections = ", ".join(result["sections"]) or "none"
        lines += [
            f"## {i}. {question}",
            "",
            f"- **Answer:** {result['answer']}",
            f"- **Sections used:** {sections}",
            f"- **A good answer contains:** {expected}",
            f"- **Check:** {verdict}",
            "",
        ]
    Path(path).write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    rows = run(build_index())
    out = Path(__file__).resolve().parent / "answers.md"
    write_markdown(rows, out, "Policy Q&A answers",
                   "Policy: data/loan_policy.txt, chunk size 300, overlap 50.")
    print("\nwritten:", out)
