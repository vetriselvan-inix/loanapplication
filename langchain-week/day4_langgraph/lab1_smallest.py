"""Day 4, lab 1: the smallest graph. Two boxes turn "hello" into "HELLO!".

Run:  uv run python day4_langgraph\\lab1_smallest.py
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph


class State(TypedDict):
    text: str


def shout(state: State):
    return {"text": state["text"].upper()}


def exclaim(state: State):
    return {"text": state["text"] + "!"}


builder = StateGraph(State)
builder.add_node("shout", shout)
builder.add_node("exclaim", exclaim)
builder.add_edge(START, "shout")
builder.add_edge("shout", "exclaim")
builder.add_edge("exclaim", END)
graph = builder.compile()

if __name__ == "__main__":
    print(graph.invoke({"text": "hello"}))
