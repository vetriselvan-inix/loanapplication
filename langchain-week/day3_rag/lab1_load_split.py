"""Day 3, Lab 1: load the policy and split it into chunks. No model involved."""

import sys
from pathlib import Path

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from policy_rag import add_metadata

sys.stdout.reconfigure(encoding="utf-8")  # the Windows console cannot print the rupee sign otherwise

POLICY = Path(__file__).resolve().parent.parent / "data" / "loan_policy.txt"

docs = TextLoader(str(POLICY), encoding="utf-8").load()
chunks = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50).split_documents(docs)

add_metadata(chunks)  # shared with the later labs, see policy_rag.py

print("characters in the document:", len(docs[0].page_content))
print("number of chunks:", len(chunks))
for i, chunk in enumerate(chunks):
    print(f"\n--- chunk {i} ({len(chunk.page_content)} characters) ---")
    print(chunk.page_content)
    print("metadata:", chunk.metadata)

# With size 300 every policy line fits whole, so the splitter cuts between lines and
# nothing needs to overlap. chunk_overlap only matters when a line has to be cut in half.
# Use small chunks to force that, and look at what two neighbouring chunks share.
small = RecursiveCharacterTextSplitter(chunk_size=100, chunk_overlap=30).split_documents(docs)
print("\n\n===== chunk_size=100, chunk_overlap=30:", len(small), "chunks =====")
for i in range(len(small) - 1):
    a, b = small[i].page_content, small[i + 1].page_content
    for k in range(min(len(a), len(b)), 5, -1):
        if a.endswith(b[:k]):
            print(f"\nchunk {i} ends with:    {a[-k:]!r}")
            print(f"chunk {i + 1} starts with: {b[:k]!r}")
            break
    else:
        continue
    break
