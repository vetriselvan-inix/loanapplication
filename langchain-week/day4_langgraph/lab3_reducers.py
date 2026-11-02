"""Day 4, lab 3: reducers. The same three boxes run twice. With a plain `log` field each box
overwrites the one before it; with Annotated[list[str], operator.add] each box appends.

Run:  uv run python day4_langgraph\\lab3_reducers.py
"""

import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph


class PlainState(TypedDict):
    text: str
    log: list[str]  # no rule given: a new value replaces the old one


class AppendState(TypedDict):
    text: str
    log: Annotated[list[str], operator.add]  # the rule: new entries are added to the old list


def first(state):
    return {"text": state["text"].upper(), "log": ["first"]}


def second(state):
    return {"text": state["text"] + "!", "log": ["second"]}


def third(state):
    return {"text": state["text"] + "?", "log": ["third"]}


def build(state_type):
    builder = StateGraph(state_type)
    for name, fn in (("first", first), ("second", second), ("third", third)):
        builder.add_node(name, fn)
    builder.add_edge(START, "first")
    builder.add_edge("first", "second")
    builder.add_edge("second", "third")
    builder.add_edge("third", END)
    return builder.compile()


plain_graph = build(PlainState)
append_graph = build(AppendState)

if __name__ == "__main__":
    print("plain log:   ", plain_graph.invoke({"text": "hi", "log": []})["log"])
    print("appending log:", append_graph.invoke({"text": "hi", "log": []})["log"])
