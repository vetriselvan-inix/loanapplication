"""Tools for the policy agent: the policy search, and a percentage calculator for fees."""

from decimal import ROUND_HALF_UP, Decimal

from langchain.tools import tool
from policy_rag import build_index

_store = build_index()  # embeds the policy once, when this module is imported


@tool
def search_policy(query: str) -> str:
    """Search the company's loan policy document for rules, eligibility conditions, loan
    amounts and tenures, interest rates, fees and charges, prepayment, required documents
    and disbursal. Use it for questions about what the policy says. Do not use it for
    calculations or for facts about one customer. Returns the three closest passages,
    each starting with its section number, so cite those numbers in the answer."""
    hits = _store.similarity_search(query, k=3)
    return "\n\n".join(f"[{hit.metadata['document']}]\n{hit.page_content}" for hit in hits)


@tool
def percent_of(amount: float, percent: float) -> dict | str:
    """Calculate a percentage of an amount in rupees, for example a processing fee of
    1.5 percent of a loan amount. amount is in rupees and percent is the percentage as a
    number (1.5 means 1.5 percent). Returns the result in rupees. Returns a short message
    if the amount is not above zero or the percent is outside 0 to 100."""
    if amount <= 0:
        return "Amount must be greater than zero."
    if not 0 <= percent <= 100:
        return "Percent must be between 0 and 100."
    result = Decimal(str(amount)) * Decimal(str(percent)) / 100
    return {
        "amount": amount,
        "percent": percent,
        "result": float(result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
    }
