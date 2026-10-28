import sys

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_ollama import ChatOllama

load_dotenv()
sys.stdout.reconfigure(encoding="utf-8")  # the Windows console cannot print the rupee sign otherwise
model = ChatOllama(model="qwen3.5:9b", reasoning=False, temperature=0)

EXPECTED = {"p": 500000, "r": 11, "n": 36}  # 5 lakh, 11 percent, 36 months


def emi(p: float, r: float, n: int) -> float:
    monthly = r / (12 * 100)
    factor = (1 + monthly) ** n
    return round(p * monthly * factor / (factor - 1), 2)


# Cryptic parameter names in both versions: the docstring is the only difference.
@tool("emi_calculator", description="does maths")
def vague(p: float, r: float, n: int) -> float:
    return emi(p, r, n)


@tool(
    "emi_calculator",
    description=(
        "Calculate the monthly EMI of a loan. p is the loan amount in rupees, "
        "r is the yearly interest rate as a percent number (11 means 11 percent, not 0.11), "
        "n is the loan length in months (3 years is 36)."
    ),
)
def clear(p: float, r: float, n: int) -> float:
    return emi(p, r, n)


def run(name: str, the_tool) -> None:
    print(f"===== {name}: {the_tool.description[:60]!r}")
    agent = create_agent(
        model=model,
        tools=[the_tool],
        system_prompt="You are a careful loan assistant. Use tools for every calculation. Never guess numbers.",
    )
    result = agent.invoke({"messages": [{"role": "user", "content": "EMI for 5 lakh at 11% for 3 years?"}]})
    calls = [c for m in result["messages"] for c in (getattr(m, "tool_calls", None) or [])]
    if not calls:
        print("NO TOOL CALL. The model answered by itself.")
    for c in calls:
        args = c["args"]
        ok = all(args.get(k) == v for k, v in EXPECTED.items())
        print("tool args:", args, "->", "CORRECT" if ok else "WRONG (expected %s)" % EXPECTED)
    print("final:", result["messages"][-1].content, "\n")


run("VAGUE docstring", vague)
run("CLEAR docstring", clear)
