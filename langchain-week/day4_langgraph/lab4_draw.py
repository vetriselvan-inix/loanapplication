"""Day 4, lab 4: draw a graph. Exports the lab 2 branch graph as a Mermaid diagram, prints it,
and saves it to lab4_diagram.md so it can be previewed or pasted into any Mermaid viewer.

Run:  uv run python day4_langgraph\\lab4_draw.py
"""

from pathlib import Path

from lab2_branch import graph

if __name__ == "__main__":
    diagram = graph.get_graph().draw_mermaid()
    print(diagram)
    path = Path(__file__).resolve().parent / "lab4_diagram.md"
    path.write_text(f"```mermaid\n{diagram}```\n", encoding="utf-8")
    print(f"written: {path}")
