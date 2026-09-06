import re
from typing import Any, Dict, Optional
from pydantic import BaseModel, field_validator


# --- HUID Request ---
class HUIDRequest(BaseModel):
  huid: str

  @field_validator("huid")
  @classmethod
  def validate_huid_format(cls, v: str) -> str:
    v = v.strip().upper()
    if not re.match(r"^[A-Z0-9]{6}$", v):
      raise ValueError("HUID must be exactly 6 alphanumeric characters.")
    return v


class LicenseRequest(BaseModel):
  license_number: str



class VerificationResponse(BaseModel):
  status: str  
  is_valid: bool
  message: str
  data: Optional[Dict[str, Any]] = None