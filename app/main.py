from typing import List, Optional
from fastapi import FastAPI
from pydantic import BaseModel

from app.rag_service import ask_question


class ChatMessage(BaseModel):
  role: str  # "user" or "assistant"
  content: str  # The message text


class ChatRequest(BaseModel):
  question: str
  chat_history: Optional[List[ChatMessage]] = []  # Defaults to an empty list


app = FastAPI(title="BIS Sahayak AI Assistant")


@app.get("/")
def home():
  return {"status": "BIS Sahayak API is running online!"}


@app.post("/chat")
def chat_endpoint(request: ChatRequest):
  # Unpack the tuple (answer, sources) from rag_service
  answer, sources = ask_question(request.question, request.chat_history)

  # Return structured JSON dictionary
  return {"answer": answer, "sources": sources}