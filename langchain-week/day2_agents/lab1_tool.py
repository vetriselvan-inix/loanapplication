from langchain.tools import tool


@tool
def emi_calculator(principal: float, annual_rate_percent: float, tenure_months: int) -> float:
    """Calculate the monthly EMI of a loan.
    principal is in rupees, annual_rate_percent is like 11 for 11 percent,
    tenure_months is the loan length in months."""
    r = annual_rate_percent / (12 * 100)
    factor = (1 + r) ** tenure_months
    return round(principal * r * factor / (factor - 1), 2)


if __name__ == "__main__":
    print("name:", emi_calculator.name)
    print("description:", emi_calculator.description)
    print("args:", emi_calculator.args)

    emi = emi_calculator.invoke({"principal": 500000, "annual_rate_percent": 11, "tenure_months": 36})
    print("EMI for 5,00,000 at 11% for 36 months:", emi)

    # Done when: this is about 16,370
    assert 16360 < emi < 16380, emi
