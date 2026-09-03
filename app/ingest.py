import os
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader, UnstructuredExcelLoader

from app.config import FAISS_INDEX_PATH, embeddings_model


# ---- SWAPPABLE LOADER FUNCTION ----
def load_documents(path):
    if path.lower().endswith(".pdf"):
        loader = PyPDFLoader(path)
        docs = loader.load()

    elif path.lower().endswith((".xlsx", ".xls")):
        loader = UnstructuredExcelLoader(path, mode="elements")
        docs = loader.load()

    else:
        print(f"Skipping unsupported file: {path}")
        return []

    for doc in docs:
        doc.metadata["source_file"] = os.path.basename(doc.metadata.get("source", path))

    return docs


# ---- FILE LIST ----
file_paths = [
    r"D:\SIH2026\data\bis.pdf",
    r"D:\SIH2026\data\Sector_List.xlsx",
    r"D:\SIH2026\data\File_Published_Standards_List_2026-09-02_000251.xlsx",
]


def build_index():
    all_docs = []
    for path in file_paths:
        loaded = load_documents(path)
        all_docs.extend(loaded)
        print(f"Loaded {len(loaded)} docs from {os.path.basename(path)}")

    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
    chunks = splitter.split_documents(all_docs)

    vector_store = FAISS.from_documents(chunks, embeddings_model)
    vector_store.save_local(FAISS_INDEX_PATH)
    print(f"Saved FAISS index to '{FAISS_INDEX_PATH}' with {len(chunks)} chunks.")


if __name__ == "__main__":
    build_index()