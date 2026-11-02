"""Day 4, lab 5: a model inside a node. The read_email box calls the Day 1 reader and puts the
extracted enquiry into the state. Needs Ollama running (one model call, about 20 to 40 seconds).

Run:  uv run python day4_langgraph\\lab5_model_node.py
"""

import sys
from pathlib import Path
from typing import NotRequired, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "day1_langchain"))
from enquiry_reader import LoanEnquiry, read_enquiry  # noqa: E402
from langgraph.graph import END, START, StateGraph  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")  # the Windows console cannot print the rupee sign otherwise


class State(TypedDict):
    email: str
    enquiry: NotRequired[LoanEnquiry]  # filled in by read_email, so not part of the input


def read_email(state: State):
    return {"enquiry": read_enquiry(state["email"])}


builder = StateGraph(State)
builder.add_node("read_email", read_email)
builder.add_edge(START, "read_email")
builder.add_edge("read_email", END)
graph = builder.compile()

EMAIL = "Hi, this is Ramesh Kumar. I need 5 lakh for 3 years to renovate my house."

if __name__ == "__main__":
    state = graph.invoke({"email": EMAIL})
    enquiry = state["enquiry"]
    print(f"email:   {state['email']}")
    print(f"amount:  {enquiry.amount}")
    print(f"tenure:  {enquiry.tenure_months} months")
    print(f"purpose: {enquiry.purpose}")
