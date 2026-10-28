import re
from pathlib import Path
from typing import Literal, Optional

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field

load_dotenv()

FIELDS = ["customer_name", "amount", "tenure_months", "purpose"]


class LoanEnquiry(BaseModel):
    customer_name: Optional[str] = Field(None, description="Customer's name exactly as written; may be a first name only. Null only if no name is given")
    amount: Optional[float] = Field(None, description="Loan amount in rupees")
    tenure_months: Optional[int] = Field(None, description="Tenure converted to months")
    purpose: Optional[str] = Field(None, description="Why the loan is needed")
    confidence: Literal["high", "medium", "low"] = Field("low", description="How sure you are about the extracted values")
    missing_fields: list[str] = Field(default_factory=list, description="Names of the fields that are not stated in the email")
    error: Optional[str] = Field(None, description="Set only when the email could not be read")


model = ChatOllama(model="qwen3.5:9b", reasoning=False, temperature=0)

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Extract the loan enquiry from the customer's email.\n"
            "Rules:\n"
            "- Never guess. If a value is not stated, return null for it.\n"
            "- customer_name: give the full name exactly as written (e.g. 'Ramesh Kumar'). "
            "If only a first name is written, give just that (e.g. 'Suresh here' gives 'Suresh').\n"
            "- amount is in rupees: 1 lakh or 1L = 100000, so 25L = 2500000; Rs 12,00,000 = 1200000.\n"
            "- tenure_months is always in months: 1 year = 12 months.\n"
            "- purpose is only filled when the customer states a reason for the loan.\n"
            "- confidence is high when every field is stated, medium when one or two are missing, "
            "low when three or more are missing.\n"
            "- missing_fields lists the names of the fields that are null.",
        ),
        ("human", "{email}"),
    ]
)
chain = prompt | model.with_structured_output(LoanEnquiry)


def _finish(result: LoanEnquiry) -> LoanEnquiry:
    """Derive missing_fields from the data itself instead of trusting the model."""
    result.missing_fields = [f for f in FIELDS if getattr(result, f) is None]
    return result


def _could_not_read() -> LoanEnquiry:
    return LoanEnquiry(confidence="low", missing_fields=list(FIELDS), error="could not read")


def read_enquiry(text: str) -> LoanEnquiry:
    """Read one email into a LoanEnquiry. One retry, then a clean fallback."""
    if not text or not text.strip():
        return _could_not_read()
    for _attempt in range(2):
        try:
            return _finish(chain.invoke({"email": text}))
        except Exception:
            continue
    return _could_not_read()


def read_enquiries(texts: list[str]) -> list[LoanEnquiry]:
    """Read many emails with .batch; any that fail go through read_enquiry (retry, then fallback)."""
    outputs = chain.batch([{"email": t} for t in texts], return_exceptions=True)
    results = []
    for text, out in zip(texts, outputs):
        if isinstance(out, Exception):
            results.append(read_enquiry(text))
        else:
            results.append(_finish(out))
    return results


def load_emails() -> list[str]:
    path = Path(__file__).parent.parent / "data" / "enquiries.txt"
    lines = path.read_text(encoding="utf-8").splitlines()
    return [re.sub(r"^\d+\.\s*", "", line).strip() for line in lines if line.strip()]


def format_table(results: list[LoanEnquiry]) -> str:
    header = f"{'#':<3}{'name':<16}{'amount':>12}{'months':>8}  {'purpose':<28}{'conf':<8}missing"
    rows = [header, "-" * len(header)]
    for i, r in enumerate(results, 1):
        rows.append(
            f"{i:<3}{str(r.customer_name):<16}{str(r.amount):>12}{str(r.tenure_months):>8}  "
            f"{str(r.purpose)[:26]:<28}{r.confidence:<8}{','.join(r.missing_fields) or '-'}"
        )
    return "\n".join(rows)


if __name__ == "__main__":
    emails = load_emails()
    results = read_enquiries(emails)
    out = [format_table(results)]

    # Failure handling: an empty string gives a clean fallback, not a crash or a guess
    empty = read_enquiry("")
    out.append(f"\nEMPTY INPUT -> error={empty.error!r}, confidence={empty.confidence}, missing={empty.missing_fields}")

    # Checks from the assignment
    for i in (0, 1):  # emails 1 and 2 have every field filled
        for f in FIELDS:
            assert getattr(results[i], f) is not None, f"email {i + 1}: {f} should be filled"
    assert "amount" in results[3].missing_fields, "email 4: amount should be missing"
    assert results[4].amount == 2_500_000, "email 5: 25L should be 2500000"
    assert results[4].tenure_months == 60, "email 5: 5 years should be 60 months"
    assert empty.error == "could not read"
    out.append("\nALL ASSERTS PASSED")

    text = "\n".join(out)
    print(text)
    (Path(__file__).parent / "results.txt").write_text(text + "\n", encoding="utf-8")
