"""Day 3 assignment: answer a policy question from the policy only, and say which sections were used."""

import os
import re
import sys

from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from policy_rag import build_index, sections_in

sys.stdout.reconfigure(encoding="utf-8")  # the Windows console cannot print the rupee sign otherwise

load_dotenv()

NOT_FOUND = "I could not find this in the policy."

PROMPT = """You answer questions about a loan policy.
Rules:
- Use only the context below. Do not use any other knowledge.
- If the answer is not in the context, reply exactly: {not_found}
- After each fact, cite its section number in square brackets, like [3.2].
- Keep the answer short, but include every condition, charge or exception in the cited section that applies to the question.
- If the policy gives only a range or a general rule, give that. Never make up an exact figure.
- Do not do calculations. State the rule and its section instead.

Context:
{context}

Question: {question}"""

_model = ChatOllama(
    model=os.environ.get("OLLAMA_MODEL", "qwen3.5:9b"),
    reasoning=False,  # thinking mode makes each call minutes slower on this CPU
    temperature=0,
)
_default_store = None


def ask_policy(question: str, store=None) -> dict:
    """Return {"answer": str, "sections": [str], "retrieved": [str]}.

    sections  = the section numbers the answer cites, kept only if they really appear in the
                retrieved text (a number the model invented is dropped). Empty when the
                answer is "I could not find this in the policy."
    retrieved = every section number in the three chunks that were fetched.
    Pass a store built with build_index(...) to try another chunk size or policy file.
    """
    global _default_store
    if store is None:
        if _default_store is None:
            _default_store = build_index()
        store = _default_store

    hits = store.similarity_search(question, k=3)
    retrieved = [number for hit in hits for number in sections_in(hit.page_content)]
    context = "\n\n".join(hit.page_content for hit in hits)
    answer = _model.invoke(
        PROMPT.format(not_found=NOT_FOUND, context=context, question=question)
    ).content.strip()

    if NOT_FOUND in answer:
        sections = []
    else:
        cited = re.findall(r"\[(\d+\.\d+)\]", answer)
        sections = [s for s in dict.fromkeys(cited) if s in retrieved]
    return {"answer": answer, "sections": sections, "retrieved": retrieved}


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "What is the minimum age?"
    result = ask_policy(question)
    print("QUESTION:", question)
    print("ANSWER:", result["answer"])
    print("SECTIONS USED:", ", ".join(result["sections"]) or "-")
