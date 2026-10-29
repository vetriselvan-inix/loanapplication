"""Checks of ask_policy(). Uses the chat model, so Ollama must be running (about 20 s per question)."""

import sys

from ask_policy import NOT_FOUND, ask_policy

sys.stdout.reconfigure(encoding="utf-8")


def test_answer_comes_with_its_section_number():
    r = ask_policy("What is the minimum age?")
    print(r)
    assert "21" in r["answer"]
    assert r["sections"] == ["1.1"]


def test_unanswerable_question_is_declined_with_no_sections():
    r = ask_policy("What is the policy on gold loans?")
    print(r)
    assert r["answer"] == NOT_FOUND
    assert r["sections"] == []


def test_invented_section_numbers_are_dropped(monkeypatch=None):
    # sections only ever contains numbers that really appear in the retrieved text
    r = ask_policy("How soon is the money paid out?")
    print(r)
    assert set(r["sections"]) <= set(r["retrieved"])
    assert "5.1" in r["sections"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name, "\n", flush=True)
