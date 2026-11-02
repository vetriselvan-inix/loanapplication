"""Day 4, lab 2: a branch. A check box looks at the text, and a diamond sends short and long
texts to different boxes. stream_mode="updates" prints what each box returned, which proves
which path was taken.

Run:  uv run python day4_langgraph\\lab2_branch.py
"""

from typing import NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph

LIMIT = 10  # up to this many characters is "short"


class State(TypedDict):
    text: str
    length: NotRequired[int]  # filled in by check
    result: NotRequired[str]  # filled in by a handler


def check(state: State):
    return {"length": len(state["text"])}


def short_or_long(state: State) -> str:
    """The diamond: reads the state and returns the name to route on."""
    return "short" if len(state["text"]) <= LIMIT else "long"


def handle_short(state: State):
    return {"result": f"short text, kept as it is: {state['text']}"}


def handle_long(state: State):
    return {"result": f"long text, cut to {LIMIT} characters: {state['text'][:LIMIT]}..."}


builder = StateGraph(State)
builder.add_node("check", check)
builder.add_node("handle_short", handle_short)
builder.add_node("handle_long", handle_long)
builder.add_edge(START, "check")
builder.add_conditional_edges("check", short_or_long, {"short": "handle_short", "long": "handle_long"})
builder.add_edge("handle_short", END)
builder.add_edge("handle_long", END)
graph = builder.compile()

if __name__ == "__main__":
    for text in ("hello", "this text is much longer than ten characters"):
        print(f"input: {text!r}")
        for update in graph.stream({"text": text}, stream_mode="updates"):
            print("  ", update)
        print()
