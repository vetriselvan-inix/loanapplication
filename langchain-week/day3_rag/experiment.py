"""Day 3 experiment: run the ten questions at two chunk sizes and compare.

Run:  uv run python -W ignore day3_rag\\experiment.py
Takes about 8 minutes (20 questions, one model call each).
Writes answers_chunk300.md, answers_chunk80.md and experiment_comparison.md.
"""

import sys
from pathlib import Path

from policy_rag import build_index
from run_questions import run, write_markdown

sys.stdout.reconfigure(encoding="utf-8")  # the Windows console cannot print the rupee sign otherwise

HERE = Path(__file__).resolve().parent
SIZES = (300, 80)  # 300 is the normal setting; 80 cuts rules into fragments (see Lab 4)

results = {}
for size in SIZES:
    store = build_index(chunk_size=size)
    results[size] = run(store, label=f"[{size}] ")
    write_markdown(
        results[size],
        HERE / f"answers_chunk{size}.md",
        f"Policy Q&A answers at chunk size {size}",
        f"Policy: data/loan_policy.txt, chunk size {size}, overlap 50.",
    )

normal, small = results[SIZES[0]], results[SIZES[1]]
lines = [
    f"# Chunk size {SIZES[0]} against {SIZES[1]}",
    "",
    "| # | Question | Check at 300 | Check at 80 | Sections at 300 | Sections at 80 | Answer changed? |",
    "|---|---|---|---|---|---|---|",
]
changed = 0
for a, b in zip(normal, small):
    same = a[2]["answer"].strip() == b[2]["answer"].strip()
    changed += 0 if same else 1
    lines.append(
        f"| {a[0]} | {a[1]} | {a[4]} | {b[4]} | {', '.join(a[2]['sections']) or '-'} | "
        f"{', '.join(b[2]['sections']) or '-'} | {'no' if same else 'yes'} |"
    )
lines += ["", f"{changed} of {len(normal)} answers changed.", ""]
for a, b in zip(normal, small):
    if a[2]["answer"].strip() != b[2]["answer"].strip():
        lines += [
            f"## Question {a[0]}: {a[1]}",
            "",
            f"- **At 300:** {a[2]['answer']}",
            f"- **At 80:** {b[2]['answer']}",
            "",
        ]
(HERE / "experiment_comparison.md").write_text("\n".join(lines), encoding="utf-8")
print("\nwritten: experiment_comparison.md,", ", ".join(f"answers_chunk{s}.md" for s in SIZES), flush=True)
