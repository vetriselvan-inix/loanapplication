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

# The | pipe: the filled prompt flows into the model that returns a LoanEnquiry
chain = prompt | model.with_structured_output(LoanEnquiry)

emails = [
    "Hi, I'm Ramesh Kumar. I need a loan of 5 lakh rupees for 3 years to renovate my house.",
    "need money urgently for my shop, around 2 lakhs, can repay in 18 months. - Imran",
    "Good morning, I want to know if I can get a loan for buying a two-wheeler. My name is Priya.",
]

# Part 1: batch runs the chain on all inputs in one call and returns a list
start = time.time()
results = chain.batch([{"email": e} for e in emails])
print(f"BATCH: {len(results)} results in {time.time() - start:.0f}s")
for r in results:
    print(type(r).__name__, r)

# Part 2: stream the plain model and print each piece as it arrives
print("\nSTREAM:")
for chunk in model.stream("Explain what an EMI is in two sentences."):
    print(chunk.content, end="", flush=True)
print()

# Done when: batch returns 3 objects and streaming prints gradually.
