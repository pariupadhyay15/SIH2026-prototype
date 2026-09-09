import json
import math
import os
from typing import List, Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.mock_compliance_db import MOCK_COMPLIANCE_DB
from app.mock_huid_db import MOCK_HUID_DB
from app.mock_license_db import MOCK_LICENSE_DB
from app.rag_service import ask_question
from app.schemas import HUIDRequest, LicenseRequest, VerificationResponse



class ChatMessage(BaseModel):
  role: str
  content: str


class ChatRequest(BaseModel):
  question: str
  chat_history: Optional[List[ChatMessage]] = []



app = FastAPI(title="BIS Sahayak AI Assistant")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
  return {"status": "BIS Sahayak API is running online!"}



@app.post("/chat")
def chat_endpoint(request: ChatRequest):
  try:
    answer, sources = ask_question(request.question, request.chat_history)
    return {"answer": answer, "sources": sources}
  except Exception as e:
    print(f"Error in chat endpoint: {e}")
    return {
        "answer": (
            "I encountered a temporary issue retrieving the detailed standard"
            " parameters. Please try asking again in a moment."
        ),
        "sources": [],
    }



@app.post("/verify/huid", response_model=VerificationResponse)
def verify_huid(request: HUIDRequest):
  huid_code = request.huid

  if huid_code in MOCK_HUID_DB:
    return VerificationResponse(
        status="SUCCESS",
        is_valid=True,
        message="HUID Record Verified Successfully",
        data=MOCK_HUID_DB[huid_code],
    )

  return VerificationResponse(
      status="NOT_FOUND",
      is_valid=False,
      message=(
          f"Record Not Found: HUID '{huid_code}' is not registered in the"
          " national database."
      ),
      data=None,
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
          data=record,
      )

  return VerificationResponse(
      status="NOT_FOUND",
      is_valid=False,
      message=(
          f"Record Not Found: Licence '{request.license_number}' is not active"
          " or registered."
      ),
      data=None,
  )



def haversine_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
  """Calculates Great Circle distance in KM between two coordinates."""
  R = 6371.0
  dlat = math.radians(lat2 - lat1)
  dlon = math.radians(lon2 - lon1)

  a = (
      math.sin(dlat / 2) ** 2
      + math.cos(math.radians(lat1))
      * math.cos(math.radians(lat2))
      * math.sin(dlon / 2) ** 2
  )


  a = min(1.0, max(0.0, a))
  c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
  return R * c


def load_bis_centres():
  file_path = "complete_bis_centres.json"
  if not os.path.exists(file_path):
    file_path = os.path.join("app", "complete_bis_centres.json")

  if os.path.exists(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
      return json.load(f)
  return []



@app.get("/bis-centres")
def get_bis_centres(
    city: Optional[str] = Query(None),
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
    radius: Optional[float] = Query(25.0),
):
  centres = load_bis_centres()
  filtered = []

  
  if lat is not None and lon is not None:
    for centre in centres:
      c_lat = centre.get("latitude")
      c_lon = centre.get("longitude")

      if c_lat is not None and c_lon is not None:
        dist = haversine_distance(lat, lon, float(c_lat), float(c_lon))
        if dist <= radius:
          centre_entry = centre.copy()
          centre_entry["distance_km"] = round(dist, 2)
          filtered.append(centre_entry)

    
    filtered.sort(key=lambda x: x["distance_km"])

  # Priority 2: City Name Filter
  elif city and city.strip():
    city_clean = city.strip().lower()
    for centre in centres:
      if city_clean in centre.get("city", "").lower():
        filtered.append(centre)

  
  else:
    filtered = centres

  return {"success": True, "count": len(filtered), "data": filtered}


# --- Compliance Journey Endpoints ---
@app.get("/compliance/products")
def get_compliance_products():
  """Returns summary list of available demo products for UI cards."""
  products_summary = [
      {
          "product_id": key,
          "product_name": data["product_name"],
          "category": data["category"],
      }
      for key, data in MOCK_COMPLIANCE_DB.items()
  ]
  return {"success": True, "products": products_summary}


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