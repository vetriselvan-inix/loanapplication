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


def label(message) -> str:
    kind = type(message).__name__
    if kind == "HumanMessage":
        return "HUMAN REQUEST (you asked)"
    if kind == "ToolMessage":
        return "TOOL RESULT (your Python code answered)"
    if kind == "AIMessage" and message.tool_calls:
        return "MODEL DECISION TO CALL A TOOL (the model asked, it did not run anything)"
    return "FINAL ANSWER (the model wrote it from the tool result)"


for i, message in enumerate(result["messages"], 1):
    print(f"--- {i}. {type(message).__name__}: {label(message)}")
    if getattr(message, "tool_calls", None):
        for call in message.tool_calls:
            print("    tool:", call["name"], "args:", call["args"])
    if message.content:
        print("    content:", message.content)


