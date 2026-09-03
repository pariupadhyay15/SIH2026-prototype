from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.rag_service import ask_question


app = FastAPI(
    title="BIS RAG ML Service",
    version="1.0.0"
)


class ChatRequest(BaseModel):
    question: str


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/chat")
def chat(request: ChatRequest):
    try:
        answer, sources = ask_question(request.question)
        return {
            "answer": answer,
            "sources": sources
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))