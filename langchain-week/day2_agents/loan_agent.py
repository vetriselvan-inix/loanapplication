"""Day 2 assignment: a read-only loan assistant that uses the loan app's real data.

It can look up a customer, check eligibility, quote the interest rate and calculate an
EMI. It cannot apply for, approve or change anything.

Chat:  uv run python day2_agents\\loan_agent.py
Demo:  uv run python day2_agents\\loan_agent.py --demo   (six fixed questions, saved to traces.txt)
"""

import os
import sys
from pathlib import Path

from langchain.agents import create_agent
from langchain_ollama import ChatOllama
from loan_tools import check_eligibility, emi_calculator, get_customer, get_interest_rate

sys.stdout.reconfigure(encoding="utf-8")  # the Windows console cannot print the rupee sign otherwise

SYSTEM_PROMPT = """You are a careful assistant for a loan application. You only answer questions about loans: eligibility, interest rates and EMI.
Rules:
- Use the tools for every number, rate, EMI and eligibility answer. Never guess or calculate yourself.
- If the user gives a tenure but no interest rate, call get_interest_rate with the tenure and use that rate.
- If a customer id, amount or tenure is missing, ask the user for it. Never invent one.
- If a tool returns a message saying something was not found or is invalid, tell the user that plainly.
- The credit score is calculated by the system from income, existing EMI and age, from 300 to 850, and a customer needs at least 600. Report the score and failed rules from the tools; never make up a score.
- You cannot apply for, approve or change a loan. If asked to, explain that you can only check and explain.
- If the question is not about loans, say politely that you can only help with loan questions.
- Amounts are in rupees. Keep answers short."""

model = ChatOllama(
    model=os.environ.get("OLLAMA_MODEL", "qwen3.5:9b"),
    reasoning=False,  # thinking mode makes each call minutes slower on this CPU
    temperature=0,
)

agent = create_agent(
    model=model,
    tools=[get_customer, check_eligibility, get_interest_rate, emi_calculator],
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
