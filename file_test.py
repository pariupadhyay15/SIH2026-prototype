import glob
import os

from app.config import embeddings_model
from app.ingest import load_documents
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS


# ---- auto-fetch all files from a folder ----
folder = r"D:\SIH2026\data"
file_paths = glob.glob(os.path.join(folder, "*.pdf")) + glob.glob(os.path.join(folder, "*.xlsx"))

print(f"Found {len(file_paths)} files:")
for p in file_paths:
    print(" -", os.path.basename(p))

all_docs = []
for path in file_paths:
    loaded = load_documents(path)
    all_docs.extend(loaded)
    print(f"Loaded {len(loaded)} docs from {os.path.basename(path)}")

if not all_docs:
    print("No documents loaded — check your files/paths.")
    exit()

# ---- show raw extracted text (to check if text extraction worked) ----
print("\n--- Sample extracted text from first doc ---")
print(all_docs[0].page_content[:500])

# ---- build a quick test index and retrieve ----
splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
chunks = splitter.split_documents(all_docs)

vector_store = FAISS.from_documents(chunks, embeddings_model)
retriever = vector_store.as_retriever(search_type="similarity", search_kwargs={"k": 4})

question = input("\nAsk a test question: ")
retrieved_docs = retriever.invoke(question)

print(f"\nRetrieved {len(retrieved_docs)} chunks:\n")
for i, doc in enumerate(retrieved_docs, 1):
    print(f"--- Chunk {i} (source: {doc.metadata.get('source_file')}) ---")
    print(doc.page_content[:400])
    print()