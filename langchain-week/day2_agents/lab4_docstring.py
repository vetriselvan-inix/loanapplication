import sys

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_ollama import ChatOllama

load_dotenv()
sys.stdout.reconfigure(encoding="utf-8")  # the Windows console cannot print the rupee sign otherwise
model = ChatOllama(model="qwen3.5:9b", reasoning=False, temperature=0)


# Same name, same body and same type hints as lab1_tool.py. Only the docstring is different.
@tool
def emi_calculator(principal: float, annual_rate_percent: float, tenure_months: int) -> float:
    """does maths"""
    r = annual_rate_percent / (12 * 100)
    factor = (1 + r) ** tenure_months
    return round(principal * r * factor / (factor - 1), 2)


print("DESCRIPTION THE MODEL SEES:", repr(emi_calculator.description), "\n")

agent = create_agent(
    model=model,
    tools=[emi_calculator],
    system_prompt="You are a careful loan assistant. Use tools for every calculation. Never guess numbers.",
)

result = agent.invoke({"messages": [{"role": "user", "content": "EMI for 5 lakh at 11% for 3 years?"}]})

for i, message in enumerate(result["messages"], 1):
    print(f"--- {i}. {type(message).__name__}")
    for call in getattr(message, "tool_calls", None) or []:
        print("    tool:", call["name"], "args:", call["args"])
    if message.content:
        print("    content:", message.content)

# Compare with lab3_messages.py: did the model still call the tool, and with the right arguments?
