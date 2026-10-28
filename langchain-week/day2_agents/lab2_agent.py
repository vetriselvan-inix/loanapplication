import sys

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_ollama import ChatOllama

from lab1_tool import emi_calculator

load_dotenv()
sys.stdout.reconfigure(encoding="utf-8")  # the Windows console cannot print the rupee sign otherwise
model = ChatOllama(model="qwen3.5:9b", reasoning=False, temperature=0)

agent = create_agent(
    model=model,
    tools=[emi_calculator],
    system_prompt="You are a careful loan assistant. Use tools for every calculation. Never guess numbers.",
)

result = agent.invoke({"messages": [{"role": "user", "content": "EMI for 5 lakh at 11% for 3 years?"}]})
print(result["messages"][-1].content)

# Proof the model asked for the tool instead of calculating it itself
tool_calls = [call for m in result["messages"] for call in getattr(m, "tool_calls", [])]
print("\nTOOL CALLS:", tool_calls)


