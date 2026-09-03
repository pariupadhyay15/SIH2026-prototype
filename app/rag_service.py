from langchain_community.vectorstores import FAISS
from langchain_core.prompts import PromptTemplate

from app.config import FAISS_INDEX_PATH, embeddings_model, llm


# -----------------------------
# Load saved FAISS index (built by ingest.py)
# -----------------------------

vector_store = FAISS.load_local(
    FAISS_INDEX_PATH,
    embeddings_model,
    allow_dangerous_deserialization=True
)


# -----------------------------
# Retriever
# -----------------------------

retriever = vector_store.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 8}
)


# -----------------------------
# Prompt
# -----------------------------

prompt = PromptTemplate(
    template="""
You are a helpful assistant.

Answer ONLY from the provided context.

If the context is insufficient, just say you don't know
and explain that the provided documents do not contain
enough information.

Do not mention sources in your answer text.
Answer like a human chatbot.

Context:
{context}

Question:
{question}
""",
    input_variables=["context", "question"]
)


# -----------------------------
# Format documents
# -----------------------------

def format_docs(retrieved_docs):
    context_text = "\n\n".join(
        f"[Source: {doc.metadata.get('source_file', 'unknown')}]\n"
        f"{doc.page_content}"
        for doc in retrieved_docs
    )
    return context_text


# -----------------------------
# Function for API
# -----------------------------

def ask_question(user_question):
    retrieved_docs = retriever.invoke(user_question)
    context_text = format_docs(retrieved_docs)

    final_prompt = prompt.invoke({"context": context_text, "question": user_question})
    answer = llm.invoke(final_prompt)

    sources = list(set(
        doc.metadata.get("source_file", "unknown") for doc in retrieved_docs
    ))

    return answer.content, sources