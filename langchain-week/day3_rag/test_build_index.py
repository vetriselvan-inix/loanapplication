"""Checks of build_index(). Uses the embedding model, so Ollama must be running."""

import sys

from policy_rag import DATA, build_index

sys.stdout.reconfigure(encoding="utf-8")


def test_index_holds_every_chunk_with_the_document_name():
    store = build_index()
    docs = list(store.store.values())
    print("chunks stored:", len(docs))
    assert len(docs) == 9
    assert {d["metadata"]["document"] for d in docs} == {"loan_policy.txt"}


def test_search_finds_the_disbursal_rule_by_meaning():
    top = build_index().similarity_search("How soon is the money paid out?", k=1)[0]
    print("top hit:", top.page_content[:60].replace("\n", " "))
    assert "5.1" in top.page_content


def test_chunk_size_changes_the_index():
    small = len(build_index(chunk_size=80).store)
    normal = len(build_index(chunk_size=300).store)
    big = len(build_index(chunk_size=2000).store)
    print("chunks at 80 / 300 / 2000:", small, normal, big)
    assert small > normal > big == 1


def test_a_different_policy_file_can_be_indexed():
    store = build_index(policy=DATA / "loan_policy_guide.txt")
    top = store.similarity_search("What is the minimum monthly income for salaried applicants?", k=1)[0]
    print("guide policy top hit:", top.page_content[:60].replace("\n", " "))
    assert "25,000" in top.page_content
    assert top.metadata["document"] == "loan_policy_guide.txt"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name, "\n")
