"""Day 2 assignment: a read-only loan assistant that uses the loan app's real data.

It can look up a customer, check eligibility, quote the interest rate and calculate an
EMI. Since Day 3 it can also answer from the loan policy document (search_policy) and work
out percentage fees (percent_of). It cannot apply for, approve or change anything.

Chat:  uv run python day2_agents\\loan_agent.py
Demo:  uv run python day2_agents\\loan_agent.py --demo   (six fixed questions, saved to traces.txt)
"""

import os
import sys
from pathlib import Path

from langchain.agents import create_agent
from langchain_ollama import ChatOllama
from loan_tools import check_eligibility, emi_calculator, get_customer, get_interest_rate

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "day3_rag"))
from policy_tools import percent_of, search_policy  # noqa: E402  (Day 3 tools; builds the policy index on import)

sys.stdout.reconfigure(encoding="utf-8")  # the Windows console cannot print the rupee sign otherwise

SYSTEM_PROMPT = """You are an assistant for a loan application. You only help with loans: eligibility, interest rates, EMI and what the loan policy says. Amounts are in rupees. Keep answers short.

Choose the tool by the kind of question:
- The user gives an amount, a tenure and a rate and wants the EMI: call emi_calculator at once. Do not ask for a customer id.
- The user gives a tenure but no rate: call get_interest_rate, then use that rate.
- A fee, charge, document, prepayment, disbursal or any other rule of the policy: call search_policy and answer only from the text it returns. Cite the section number that appears in that text, like [3.2]. Never cite a section that is not in the returned text.
- A fee that is a percentage of an amount, such as the processing fee on a loan amount: call search_policy for the percentage, then call percent_of with that percentage and the amount. Give the rupee amount, and repeat any condition such as "plus applicable taxes".
- A question about one specific customer (eligibility, income, existing loans, credit score): call get_customer and check_eligibility. Ask for a customer id only when the question is about a customer and none is given.
- A question with several parts: call every tool it needs.

Rules:
- Never calculate or guess a number yourself.
- Never say the policy lacks something unless you have called search_policy first. If it really does, say: I could not find this in the policy.
- If a tool says something was not found or is invalid, tell the user plainly.
- The credit score (300 to 850) is calculated by the system and at least 600 is needed. Report the score from the tools and never make one up.
- You cannot apply for, approve or change a loan. You can only check and explain.
- If the question is not about loans, say politely that you can only help with loan questions."""

model = ChatOllama(
    model=os.environ.get("OLLAMA_MODEL", "qwen3.5:9b"),
    reasoning=False,  # thinking mode makes each call minutes slower on this CPU
    temperature=0,
)

agent = create_agent(
    model=model,
    tools=[
        get_customer,
        check_eligibility,
        get_interest_rate,
        emi_calculator,
        search_policy,
        percent_of,
    ],
    system_prompt=SYSTEM_PROMPT,
)

QUESTIONS = [
    "What is the EMI for 3,00,000 at 10.5% for 24 months?",
    "Is customer 29 eligible for a loan of 5,00,000 for 36 months?",
    "Is customer 4 eligible for a loan of 4,00,000 for 24 months?",
    "Is customer 999 eligible for a loan of 1,00,000 for 12 months?",
    "What is the capital of France?",
    "Can I get a loan?",
]


def show(messages, out):
    """Write the message sequence so the order of tool calls is visible."""
    for m in messages:
        kind = type(m).__name__
        calls = getattr(m, "tool_calls", None)
        if calls:
            for call in calls:
                out(f"  {kind} -> tool call: {call['name']}({call['args']})")
        elif kind == "ToolMessage":
            out(f"  ToolMessage ({m.name}): {m.content}")
        else:
            out(f"  {kind}: {m.content}")


def chat():
    """Talk to the agent in the terminal. The whole conversation is sent each turn, so follow-ups work."""
    print("Loan assistant (read-only). Type q to quit.\n")
    history = []
    while True:
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if question.lower() in {"q", "quit", "exit"}:
            break
        if not question:
            continue
        history.append({"role": "user", "content": question})
        seen = len(history)
        result = agent.invoke({"messages": history})
        history = result["messages"]
        for m in history[seen:]:
            for call in getattr(m, "tool_calls", None) or []:
                print(f"  [tool] {call['name']}({call['args']})")
        print(f"Assistant: {history[-1].content}\n")


def main():
    path = Path(__file__).resolve().parent / "traces.txt"
    with path.open("w", encoding="utf-8") as f:

        def out(line=""):
            print(line, flush=True)
            f.write(line + "\n")

        for i, question in enumerate(QUESTIONS, 1):
            out(f"=== Q{i}: {question}")
            result = agent.invoke({"messages": [{"role": "user", "content": question}]})
            show(result["messages"], out)
            out(f"ANSWER: {result['messages'][-1].content}\n")


if __name__ == "__main__":
    if "--demo" in sys.argv:
        main()
    else:
        chat()
