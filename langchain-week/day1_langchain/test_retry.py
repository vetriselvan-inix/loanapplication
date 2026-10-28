import enquiry_reader
from enquiry_reader import LoanEnquiry, read_enquiry


class FakeChain:
    """Stands in for the real chain: fails `fail_times` times, then succeeds. Counts every call."""

    def __init__(self, fail_times: int):
        self.fail_times = fail_times
        self.calls = 0

    def invoke(self, _inputs):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("simulated model failure")
        return LoanEnquiry(customer_name="Ramesh Kumar", amount=500000, tenure_months=36, purpose="house renovation", confidence="high")


def run_with(fake: FakeChain, text: str = "a normal email"):
    real = enquiry_reader.chain
    enquiry_reader.chain = fake
    try:
        return read_enquiry(text)
    finally:
        enquiry_reader.chain = real


def test_always_failing_model_is_tried_twice_then_falls_back():
    fake = FakeChain(fail_times=99)
    result = run_with(fake)
    assert fake.calls == 2, f"expected 1 try + 1 retry, got {fake.calls} calls"
    assert result.error == "could not read"
    assert result.confidence == "low"
    assert result.amount is None


def test_one_failure_is_rescued_by_the_retry():
    fake = FakeChain(fail_times=1)
    result = run_with(fake)
    assert fake.calls == 2
    assert result.error is None
    assert result.amount == 500000


def test_success_on_first_try_does_not_retry():
    fake = FakeChain(fail_times=0)
    result = run_with(fake)
    assert fake.calls == 1
    assert result.error is None


def test_empty_string_falls_back_without_calling_the_model():
    fake = FakeChain(fail_times=0)
    result = run_with(fake, text="")
    assert fake.calls == 0
    assert result.error == "could not read"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
