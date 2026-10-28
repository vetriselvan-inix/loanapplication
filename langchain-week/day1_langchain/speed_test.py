import time

from dotenv import load_dotenv
from langchain_ollama import ChatOllama

load_dotenv()
model = ChatOllama(model="qwen3.5:9b", reasoning=False, temperature=0)

start = time.time()
print(model.invoke("Say hello in one short sentence.").content)
print(f"{time.time() - start:.1f}s")
