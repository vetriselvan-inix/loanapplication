import sys

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_ollama import ChatOllama

load_dotenv()
sys.stdout.reconfigure(encoding="utf-8")  # the Windows console cannot print the rupee sign otherwise
model = ChatOllama(model="qwen3.5:9b", reasoning=False, temperature=0)


def emi(principal: float, annual_rate_percent: float, tenure_months: int) -> float:
    r = annual_rate_percent / (12 * 100)
    factor = (1 + r) ** tenure_months
    return round(principal * r * factor / (factor - 1), 2)


# # Version 1: the tool raises an exception on bad input
# @tool("emi_calculator")
# def emi_raises(principal: float, annual_rate_percent: float, tenure_months: int) -> float:
#     """Calculate the monthly EMI of a loan.
#     principal is in rupees, annual_rate_percent is like 11 for 11 percent,
#     tenure_months is the loan length in months."""
#     if tenure_months <= 0:
#         raise ValueError("Tenure must be positive")
#     return emi(principal, annual_rate_percent, tenure_months)


# Version 2: the tool returns a plain message the model can read and pass on
@tool("emi_calculator")
def emi_friendly(principal: float, annual_rate_percent: float, tenure_months: int) -> float | str:
    """Calculate the monthly EMI of a loan.
    principal is in rupees, annual_rate_percent is like 11 for 11 percent,
    tenure_months is the loan length in months.
    Returns the EMI as a number, or a short message if an input is invalid."""
    if principal <= 0:
        return "Loan amount must be positive. Please give the amount in rupees."
    if tenure_months <= 0:
        return "Tenure must be positive. Please give the loan length in months, for example 36."
    if annual_rate_percent <= 0:
        return "Interest rate must be positive. Please give it as a percent, for example 11."
    return emi(principal, annual_rate_percent, tenure_months)


# Quick checks without the model: all three bad inputs give a message, none crash
bad_inputs = [
    {"principal": 500000, "annual_rate_percent": 11, "tenure_months": -36},
    {"principal": 500000, "annual_rate_percent": 11, "tenure_months": 0},
    {"principal": 500000, "annual_rate_percent": 0, "tenure_months": 36},
]
for args in bad_inputs:
    out = emi_friendly.invoke(args)
    assert isinstance(out, str), out
    print("direct check:", args, "->", out)
assert emi_friendly.invoke({"principal": 500000, "annual_rate_percent": 11, "tenure_months": 36}) == 16369.36
print()

QUESTION = "EMI for 5 lakh at 11% for -12 months?"


def run(name: str, the_tool) -> None:
    print(f"===== {name}")
    agent = create_agent(
        model=model,
        tools=[the_tool],
        system_prompt="You are a careful loan assistant. Use tools for every calculation. Never guess numbers.",
    )
    try:
        result = agent.invoke({"messages": [{"role": "user", "content": QUESTION}]})
    except Exception as exc:
        print("CRASHED:", type(exc).__name__, "-", exc, "\n")
        return
    for i, message in enumerate(result["messages"], 1):
        print(f"--- {i}. {type(message).__name__}")
        for call in getattr(message, "tool_calls", None) or []:
            print("    tool:", call["name"], "args:", call["args"])
        if message.content:
            print("    content:", message.content)
    print()


# run("VERSION 1: tool raises an exception", emi_raises)
run("VERSION 2: tool returns a friendly message", emi_friendly)

# Done when: the agent asks the user to fix the input instead of crashing.
