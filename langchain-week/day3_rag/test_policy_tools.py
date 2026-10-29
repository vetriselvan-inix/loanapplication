"""Direct checks of percent_of. No model involved."""

import sys

from policy_tools import percent_of

sys.stdout.reconfigure(encoding="utf-8")


def test_processing_fee_on_six_lakh():
    out = percent_of.invoke({"amount": 600000, "percent": 1.5})
    print("1.5% of 6,00,000:", out)
    assert out["result"] == 9000.0


def test_rounds_to_paise():
    assert percent_of.invoke({"amount": 100, "percent": 33.333})["result"] == 33.33


def test_bad_input_returns_a_message():
    for args in ({"amount": 0, "percent": 1.5}, {"amount": -5, "percent": 1.5}):
        out = percent_of.invoke(args)
        print(args, "->", out)
        assert out == "Amount must be greater than zero."
    for args in ({"amount": 1000, "percent": -1}, {"amount": 1000, "percent": 150}):
        out = percent_of.invoke(args)
        print(args, "->", out)
        assert out == "Percent must be between 0 and 100."


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name, "\n")
