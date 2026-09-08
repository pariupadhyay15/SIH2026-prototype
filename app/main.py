import json
import math
import os
from typing import List, Optional

from fastapi import FastAPI
from pydantic import BaseModel

from app.mock_huid_db import MOCK_HUID_DB
from app.mock_license_db import MOCK_LICENSE_DB
from app.rag_service import ask_question
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


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0  # Earth's radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def load_bis_centres():
    # Looks for file in the current working directory or app/ directory
    file_path = "complete_bis_centres.json"
    if not os.path.exists(file_path):
        file_path = os.path.join("app", "complete_bis_centres.json")
    
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []



@app.get("/bis-centres")
def get_bis_centres(
    city: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    radius: Optional[float] = 25.0
):
    centres = load_bis_centres()
    filtered = []

    for centre in centres:
        
        if city and city.strip():
            if city.strip().lower() not in centre.get("city", "").lower():
                continue

        
        if lat is not None and lon is not None:
            c_lat = centre.get("latitude")
            c_lon = centre.get("longitude")
            
            if c_lat is not None and c_lon is not None:
                dist = haversine_distance(lat, lon, c_lat, c_lon)
                if dist > radius:
                    continue
                
                centre_entry = centre.copy()
                centre_entry["distance_km"] = round(dist, 2)
                filtered.append(centre_entry)
                continue

        filtered.append(centre)

    
    if lat is not None and lon is not None:
        filtered.sort(key=lambda x: x.get("distance_km", 0))

    return {
        "success": True,
        "count": len(filtered),
        "data": filtered
    }


from app.mock_compliance_db import MOCK_COMPLIANCE_DB




@app.get("/compliance/journey/{product_id}")
def get_compliance_journey(product_id: str):
  clean_key = product_id.strip().upper()

  if clean_key in MOCK_COMPLIANCE_DB:
    return {
        "success": True,
        "message": "Compliance journey retrieved successfully",
        "data": MOCK_COMPLIANCE_DB[clean_key],
    }

  
  return {
      "success": False,
      "message": (
          f"Product ID '{product_id}' not found. Available products:"
          " PROD-EARBUDS, PROD-SPEAKER, PROD-SMARTWATCH."
      ),
      "data": None,
  }