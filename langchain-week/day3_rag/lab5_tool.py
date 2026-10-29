"""Day 3, Lab 5: the policy search as a tool, used by an agent next to emi_calculator."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_ollama import ChatOllama

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "day2_agents"))
from loan_tools import emi_calculator  # noqa: E402  (the Day 2 tool; it does not touch customer data)
from policy_tools import percent_of, search_policy  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")  # the Windows console cannot print the rupee sign otherwise

load_dotenv()
model = ChatOllama(
    model=os.environ.get("OLLAMA_MODEL", "qwen3.5:9b"),
    reasoning=False,
    temperature=0,
)

SYSTEM_PROMPT = """You are a careful loan assistant.
- For questions about what the loan policy says, use search_policy and answer only from what it returns. Cite the section number in brackets, like [3.2].
- For any EMI calculation, use emi_calculator. Never calculate an EMI yourself.
- For a fee or charge that is a percentage of an amount, always give it as a rupee amount: get the percentage from the policy, then call percent_of. Never do that sum yourself, and never answer with only the percentage.
- If a question has several parts, use every tool needed to answer all of them.
- Never say the policy does not contain something unless you have searched it with search_policy first.
- If the policy does not contain the answer, say: I could not find this in the policy.
- Keep answers short.
- When a fee in the policy comes with a condition such as "plus applicable taxes", repeat that condition next to the amount."""

agent = create_agent(
    model=model,
    tools=[emi_calculator, search_policy, percent_of],
    system_prompt=SYSTEM_PROMPT,
)

QUESTIONS = [
    "How soon is the money disbursed after my documents are verified?",
    "What is the EMI for a loan of 5,00,000 at 11% for 36 months?",
    "I want 6,00,000 for 36 months at 11%. What is the EMI and the processing fee?",
]


def show(messages):
    """Print the message order so you can see which tool the agent chose."""
    for m in messages:
        kind = type(m).__name__
        calls = getattr(m, "tool_calls", None)
        if calls:
            for call in calls:
                print(f"  {kind} -> tool call: {call['name']}({call['args']})")
        elif kind == "ToolMessage":
            text = m.content if len(m.content) < 300 else m.content[:300] + " ...[cut for display]"
            print(f"  ToolMessage ({m.name}): {text}")
        else:
            print(f"  {kind}: {m.content}")


if __name__ == "__main__":
    for i, question in enumerate(QUESTIONS, 1):
        print("=" * 70)
        print(f"Q{i}: {question}")
        result = agent.invoke({"messages": [{"role": "user", "content": question}]})
        show(result["messages"])
        print(flush=True)
