from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

load_dotenv()
model = ChatOllama(model="qwen3.5:9b", reasoning=False, temperature=0)

question = "What documents do I need to apply for a personal loan?"

formal_messages = [
    SystemMessage("You are a formal, professional loan officer. Answer in two sentences."),
    HumanMessage(question),
]
print("FORMAL:")
print(model.invoke(formal_messages).content)

casual_messages = [
    SystemMessage("You are a friendly, casual helper chatting with a friend. Answer in two sentences."),
    HumanMessage(question),
]
print("\nCASUAL:")
print(model.invoke(casual_messages).content)

# Done when: the same question gives two clearly different styles.
