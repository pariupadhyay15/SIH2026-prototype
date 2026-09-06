from typing import List, Optional
from fastapi import FastAPI
from pydantic import BaseModel

from app.rag_service import ask_question
from app.mock_huid_db import MOCK_HUID_DB
from app.mock_license_db import MOCK_LICENSE_DB
from app.schemas import HUIDRequest, LicenseRequest, VerificationResponse


# --- Existing Chat Models ---
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


# --- NEW: Verification Endpoints ---

@app.post("/verify/huid", response_model=VerificationResponse)
def verify_huid(request: HUIDRequest):
    huid_code = request.huid  # Capitalized & validated by Pydantic
    
    if huid_code in MOCK_HUID_DB:
        return VerificationResponse(
            status="SUCCESS",
            is_valid=True,
            message="HUID Record Verified Successfully",
            data=MOCK_HUID_DB[huid_code]
        )
    
    return VerificationResponse(
        status="NOT_FOUND",
        is_valid=False,
        message=f"Record Not Found: HUID '{huid_code}' is not registered in the national database.",
        data=None
    )


@app.post("/verify/license", response_model=VerificationResponse)
def verify_license(request: LicenseRequest):
    clean_key = request.license_number.strip().upper().replace("/", "")
    
    for key, record in MOCK_LICENSE_DB.items():
        if key.replace("-", "") in clean_key.replace("-", ""):
            return VerificationResponse(
                status="SUCCESS",
                is_valid=True,
                message="Licence Verified Successfully",
                data=record
            )
            
    return VerificationResponse(
        status="NOT_FOUND",
        is_valid=False,
        message=f"Record Not Found: Licence '{request.license_number}' is not active or registered.",
        data=None
    )