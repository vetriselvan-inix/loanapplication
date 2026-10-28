from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

load_dotenv()
model = ChatOllama(model="qwen3.5:9b", reasoning=False, temperature=0)

# One template with a blank: {email}
prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "You are a loan assistant. Summarise the customer's email in one short sentence."),
        ("human", "{email}"),
    ]
)

emails = [
    "Hi, I'm Ramesh Kumar. I need a loan of 5 lakh rupees for 3 years to renovate my house.",
    "need money urgently for my shop, around 2 lakhs, can repay in 18 months. - Imran",
    "Good morning, I want to know if I can get a loan for buying a two-wheeler. My name is Priya.",
]

# Same template, three different emails, no edits to the prompt
for email in emails:
    filled = prompt.invoke({"email": email})
    print("EMAIL:", email)
    print("SUMMARY:", model.invoke(filled).content, "\n")

# Done when: one template gives three outputs.
