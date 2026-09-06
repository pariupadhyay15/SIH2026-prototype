from typing import List, Optional
from fastapi import FastAPI
from pydantic import BaseModel

from app.rag_service import ask_question


class ChatMessage(BaseModel):
  role: str  
  content: str  


class ChatRequest(BaseModel):
  question: str
  chat_history: Optional[List[ChatMessage]] = []  


app = FastAPI(title="BIS Sahayak AI Assistant")


@app.get("/")
def home():
  return {"status": "BIS Sahayak API is running online!"}


@app.post("/chat")
def chat_endpoint(request: ChatRequest):
  answer, sources = ask_question(request.question, request.chat_history)
  
  return {"answer": answer, "sources": sources}