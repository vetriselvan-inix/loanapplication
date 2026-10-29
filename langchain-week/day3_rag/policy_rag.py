"""Shared pieces for Day 3: load the policy, split it, tag the chunks, embed and store them."""

import re
from pathlib import Path

from langchain.embeddings import init_embeddings
from langchain_community.document_loaders import TextLoader
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter

DATA = Path(__file__).resolve().parent.parent / "data"
POLICY = DATA / "loan_policy.txt"  # the hybrid policy that matches the loan app
EMBEDDING_MODEL = "ollama:nomic-embed-text"


def add_metadata(chunks):
    """Keep only the document name on each chunk, replacing the loader's full file path."""
    for chunk in chunks:
        chunk.metadata = {"document": Path(chunk.metadata["source"]).name}
    return chunks


def sections_in(text):
    """Policy section numbers found in a text, such as ["1.3", "1.4"].

    A section number is a line that starts like "1.3 ". Matching only at the start of a
    line stops "Version 1.1" in the title from being mistaken for section 1.1.
    """
    return re.findall(r"(?m)^(\d+\.\d+)\s", text)


def load_chunks(policy=POLICY, chunk_size=300, chunk_overlap=50):
    docs = TextLoader(str(policy), encoding="utf-8").load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return add_metadata(splitter.split_documents(docs))


def build_store(chunks):
    """Embed every chunk and keep the vectors in memory (rebuilt on every run)."""
    embeddings = init_embeddings(EMBEDDING_MODEL)
    return InMemoryVectorStore.from_documents(chunks, embedding=embeddings)


def build_index(policy=POLICY, chunk_size=300, chunk_overlap=50):
    """Load the policy, split it into chunks, embed them and store them. Returns the store.

    This is the whole indexing pipeline in one call. Pass a different policy file or chunk
    size to compare how the index changes (the Day 3 experiment does exactly that).
    """
    chunks = load_chunks(policy, chunk_size, chunk_overlap)
    return build_store(chunks)
