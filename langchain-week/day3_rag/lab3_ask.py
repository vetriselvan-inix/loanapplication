"""Day 3, Lab 3: retrieve three chunks, then let the model answer only from them."""

import os
import sys

from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from policy_rag import build_store, load_chunks, sections_in

sys.stdout.reconfigure(encoding="utf-8")  # the Windows console cannot print the rupee sign otherwise

load_dotenv()
model = ChatOllama(
    model=os.environ.get("OLLAMA_MODEL", "qwen3.5:9b"),
    reasoning=False,  # thinking mode makes each call minutes slower on this CPU
    temperature=0,
)
store = build_store(load_chunks())

PROMPT = """You answer questions about a loan policy.
Rules:
- Use only the context below. Do not use any other knowledge.
- After each fact, cite its section number in square brackets, like [3.2].
- If the answer is not in the context, reply exactly: I could not find this in the policy.
- Keep the answer short, but include every condition, charge or exception in the cited section that applies to the question.
- End the answer with the section number in brackets, like [3.2], unless the answer already ends with one.

Context:
{context}

Question: {question}"""


def ask(question: str) -> dict:
    hits = store.similarity_search(question, k=3)
    context = "\n\n".join(hit.page_content for hit in hits)
    answer = model.invoke(PROMPT.format(context=context, question=question)).content
    retrieved = [number for hit in hits for number in sections_in(hit.page_content)]
    return {"answer": answer, "retrieved_sections": retrieved, "hits": hits}


QUESTIONS = [
    "What is the minimum age?",
    "What is the processing fee on a 6,00,000 loan?",
    "Can I prepay after 8 months?",
]

if __name__ == "__main__":
    for question in QUESTIONS:
        result = ask(question)
        print("=" * 70)
        print("QUESTION:", question)
        print("RETRIEVED SECTIONS:", ", ".join(result["retrieved_sections"]))
        print("ANSWER:", result["answer"], "\n", flush=True)
