import time
from typing import Optional

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field

load_dotenv()
model = ChatOllama(model="qwen3.5:9b", reasoning=False, temperature=0)


class LoanEnquiry(BaseModel):
    customer_name: Optional[str] = Field(None, description="Customer's name; a first name alone is fine. Null only if no name is given")
    amount: Optional[float] = Field(None, description="Loan amount in rupees")
    tenure_months: Optional[int] = Field(None, description="Tenure converted to months")
    purpose: Optional[str] = Field(None, description="Why the loan is needed")


extractor = model.with_structured_output(LoanEnquiry)

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Extract the loan enquiry from the customer's email.\n"
            "Rules:\n"
            "- Never guess. If a value is not stated, return null for it.\n"
            "- customer_name: a first name alone counts, e.g. 'Suresh here' gives 'Suresh'.\n"
            "- amount is in rupees: 1 lakh or 1L = 100000, so 25L = 2500000.\n"
            "- tenure_months is always in months: 1 year = 12 months.\n"
            "- purpose is only filled when the customer states a reason for the loan.",
        ),
        ("human", "{email}"),
    ]
)
chain = prompt | extractor

emails = [
    "Dear sir, Suresh here. Business expansion loan, 25L, 5 years. Also what are your interest rates?",
    "Good morning, I want to know if I can get a loan for buying a two-wheeler. My name is Priya.",
]

for email in emails:
    start = time.time()
    result = chain.invoke({"email": email})
    print("EMAIL:", email)
    print("TYPE:", type(result).__name__)
    print(result, f"({time.time() - start:.0f}s)\n")

# Done when: type(result) prints LoanEnquiry, not str.
