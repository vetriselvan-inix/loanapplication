"""Day 3, Lab 4: break the retriever on purpose with chunks that are far too small or too big."""

import os
import sys

from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from lab3_ask import PROMPT
from policy_rag import build_store, load_chunks

sys.stdout.reconfigure(encoding="utf-8")  # the Windows console cannot print the rupee sign otherwise

load_dotenv()
model = ChatOllama(
    model=os.environ.get("OLLAMA_MODEL", "qwen3.5:9b"),
    reasoning=False,
    temperature=0,
)

QUESTION = "What is the charge for prepaying my loan?"
SHOW_AT_MOST = 450  # characters of each retrieved chunk to print


def run(chunk_size: int) -> None:
    chunks = load_chunks(chunk_size=chunk_size)
    store = build_store(chunks)
    sizes = [len(c.page_content) for c in chunks]
    print("=" * 70)
    print(f"chunk_size={chunk_size}: {len(chunks)} chunks, "
          f"lengths from {min(sizes)} to {max(sizes)} characters")
    hits = store.similarity_search(QUESTION, k=3)
    for rank, hit in enumerate(hits, 1):
        text = hit.page_content
        shown = text if len(text) <= SHOW_AT_MOST else text[:SHOW_AT_MOST] + " ...[cut for display]"
        print(f"\n#{rank} retrieved chunk ({len(text)} characters):\n{shown!r}")
    context = "\n\n".join(h.page_content for h in hits)
    answer = model.invoke(PROMPT.format(context=context, question=QUESTION)).content
    print("\nANSWER:", answer, "\n", flush=True)


if __name__ == "__main__":
    print("QUESTION:", QUESTION, "\n")
    for size in (300, 80, 2000):  # 300 is the normal setting, for comparison
        run(size)
