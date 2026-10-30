"""The loan assistant. You log in first, and it only shows what your login is allowed to see.

A customer can ask about their own account; an officer can ask about any customer. The
checks happen in code and in the loan application itself, not in the prompt, so the model
cannot be talked out of them. Everything about customers goes through the app's API with
your token; the assistant never reads the database. It cannot apply for, approve or
change anything.

Chat:  uv run python day2_agents\\loan_agent.py
Demo:  uv run python day2_agents\\loan_agent.py --demo   (six fixed questions, needs an OFFICER login,
       saved to traces_login.txt; the original Day 2 record in traces.txt is left alone)

For scripted runs, set LOAN_USER and LOAN_PASSWORD in your shell instead of typing them.
"""

import os
import sys
from pathlib import Path

from api_tools import make_api_tools
from app_client import (
    AppError,
    AppSession,
    login_from_environment,
    prompt_login,
)
from calc_tools import compare_tenures, emi_calculator, get_interest_rate
from langchain.agents import create_agent
from langchain_ollama import ChatOllama

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "day3_rag"))
from policy_tools import percent_of, search_policy  # noqa: E402  (Day 3 tools; builds the policy index on import)

sys.stdout.reconfigure(encoding="utf-8")  # the Windows console cannot print the rupee sign otherwise

BASE_PROMPT = """You are an assistant for a loan application. You only help with loans: eligibility, interest rates, EMI and what the loan policy says. Amounts are in rupees. Keep answers short.

{who}

Choose the tool by the kind of question:
- The user gives an amount, a tenure and a rate and wants the EMI: call emi_calculator at once. Do not ask for a customer id.
- The user gives a tenure but no rate: call get_interest_rate, then use that rate.
- The user wants tenures compared, or asks which tenure to choose, for an amount: call compare_tenures with the amount, and with the monthly income if they give it. Present the options side by side.
- A fee, charge, document, prepayment, disbursal or any other rule of the policy: call search_policy and answer only from the text it returns. Cite the section number that appears in that text, like [3.2]. Never cite a section that is not in the returned text.
- A fee that is a percentage of an amount, such as the processing fee on a loan amount: call search_policy for the percentage, then call percent_of with that percentage and the amount. Give the rupee amount, and repeat any condition such as "plus applicable taxes".
- A question about a customer (eligibility, income, existing loans, credit score): call get_customer and check_eligibility.
- A question about why a customer has a certain credit score: call get_customer and explain the score from its credit_score_breakdown (base 300, income points, EMI points, age points). Use the numbers it returns and do not work them out yourself.
- When a customer is not eligible, explain the advice that check_eligibility returns: what could change the outcome, and what cannot.
- A question with several parts: call every tool it needs.

Rules:
- Never calculate or guess a number yourself.
- Never say the policy lacks something unless you have called search_policy first. If it really does, say: I could not find this in the policy.
- If a tool says something was not found, not allowed or invalid, tell the user plainly. Never try to get around a refusal.
- The credit score (300 to 850) is calculated by the system and at least 600 is needed. Report the score from the tools and never make one up.
- You cannot apply for, approve or change a loan. You can only check and explain.
- If the question is not about loans, say politely that you can only help with loan questions."""

model = ChatOllama(
    model=os.environ.get("OLLAMA_MODEL", "qwen3.5:9b"),
    reasoning=False,  # thinking mode makes each call minutes slower on this CPU
    temperature=0,
)

QUESTIONS = [
    "What is the EMI for 3,00,000 at 10.5% for 24 months?",
    "Is customer 29 eligible for a loan of 5,00,000 for 36 months?",
    "Is customer 4 eligible for a loan of 4,00,000 for 24 months?",
    "Is customer 999 eligible for a loan of 1,00,000 for 12 months?",
    "What is the capital of France?",
    "Can I get a loan?",
]


def system_prompt(session: AppSession) -> str:
    """The prompt tells the model who it is talking to. The real limits are enforced in code."""
    if session.is_officer:
        who = (
            f"The user is logged in as an OFFICER ({session.username}). They may ask about any "
            "customer. For a question about a customer, ask for the customer id if they have "
            "not given one."
        )
    else:
        who = (
            f"The user is logged in as a CUSTOMER (customer {session.customer_id}). 'I', 'me' "
            f"and 'my' mean customer {session.customer_id}, so never ask for a customer id and "
            "do not pass one to the customer tools. They can only see their own account. If they "
            "ask about another customer, say you can only help with their own account."
        )
    return BASE_PROMPT.format(who=who)


def build_agent(session: AppSession):
    """An agent whose customer tools are tied to this one login."""
    return create_agent(
        model=model,
        tools=[
            *make_api_tools(session),
            get_interest_rate,
            emi_calculator,
            compare_tenures,
            search_policy,
            percent_of,
        ],
        system_prompt=system_prompt(session),
    )


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


def log_in(session: AppSession) -> bool:
    """Log in from LOAN_USER and LOAN_PASSWORD if both are set, otherwise ask."""
    try:
        if login_from_environment(session):
            return True
    except AppError as problem:
        print(problem)
        return False
    return prompt_login(session)


def describe(session: AppSession) -> None:
    scope = (
        "any customer"
        if session.is_officer
        else f"your own account (customer {session.customer_id})"
    )
    print(f"Logged in as {session.username} ({session.role}). You can ask about {scope}.")


def chat():
    """Talk to the agent in the terminal. The whole conversation is sent each turn, so follow-ups work."""
    session = AppSession()
    if not log_in(session):
        print("Could not log in. Goodbye.")
        return
    describe(session)
    print("Type q to quit.\n")
    agent = build_agent(session)
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
        if not session.logged_in:  # the token ran out during that turn
            print("Your login has expired. Please log in again.")
            history = []  # one user's conversation is never carried into the next login
            if not prompt_login(session):
                break
            describe(session)
            agent = build_agent(session)


def main():
    session = AppSession()
    if not log_in(session):
        print("Could not log in. Goodbye.")
        return
    if not session.is_officer:
        print("The demo asks about several customers, so it needs an OFFICER login.")
        return
    agent = build_agent(session)
    path = Path(__file__).resolve().parent / "traces_login.txt"
    with path.open("w", encoding="utf-8") as f:

        def out(line=""):
            print(line, flush=True)
            f.write(line + "\n")

        out(f"Logged in as {session.username} ({session.role})\n")
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
