"""Day 3, Lab 2: embed the chunks and search them by meaning. No chat model involved."""

import sys

from policy_rag import build_store, load_chunks

sys.stdout.reconfigure(encoding="utf-8")  # the Windows console cannot print the rupee sign otherwise

chunks = load_chunks()
store = build_store(chunks)
print(f"embedded {len(chunks)} chunks from {chunks[0].metadata['document']}\n")

QUESTIONS = [
    "How soon is the money paid out?",  # never says "disbursal"; should find section 5.1
    "What if I pay the loan back early?",
    "How old do I have to be?",
]

for question in QUESTIONS:
    print("=" * 70)
    print("QUESTION:", question)
    for rank, (hit, score) in enumerate(store.similarity_search_with_score(question, k=3), 1):
        print(f"\n#{rank}  score {score:.3f}  ({hit.metadata['document']})")
        print(hit.page_content)
    print()
