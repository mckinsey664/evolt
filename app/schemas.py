from __future__ import annotations
from pydantic import BaseModel, EmailStr
from datetime import datetime

# ---------------------------
# Auth Schemas
# ---------------------------
class SignupRequest(BaseModel):
    name: str = ""
    email: EmailStr
    password: str
    role: str = "rider"

class LoginRequest(BaseModel):
    phone: str
    password: str

class UserOut(BaseModel):
    id: int
    email: str
    name: str | None = None
    role: str
    class Config:
        from_attributes = True

# ---------------------------
# Driver Schemas
# ---------------------------
class DriverStatusUpdate(BaseModel):
    online: bool

class LocationUpdate(BaseModel):
    lat: float
    lng: float

# ---------------------------
# Car Types
# ---------------------------
class CarTypeOut(BaseModel):
    id: int
    name: str
    base_fare: float
    per_km: float
    per_min: float
    class Config:
        from_attributes = True

# ---------------------------
# Ride Schemas
# ---------------------------
class RideRequest(BaseModel):
    rider_id: int
    pickup_lat: float
    pickup_lng: float
    drop_lat: float
    drop_lng: float
    vehicle_type: str = "economy"
    scheduled_at: Optional[datetime] = None
    notes: Optional[str] = None

    # ✅ NEW: trust user-entered names when provided
    pickup_address: Optional[str] = None
    drop_address: Optional[str] = None

# ---------------------------
# Ride Update Schema
# ---------------------------
class RideUpdate(BaseModel):
    pickup_lat: float
    pickup_lng: float
    drop_lat: float
    drop_lng: float
    scheduled_at: Optional[datetime] = None
    pickup_address: Optional[str] = None
    drop_address: Optional[str] = None


class AdminDecision(BaseModel):
    decision: str  # "approve" or "reject"
    reason: str | None = None  # reserved for future use

from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class RideOut(BaseModel):
    id: int
    status: str
    rider_id: int
    driver_id: Optional[int] = None

    rider_name: Optional[str] = None   # ✅ NEW
    rider_phone: Optional[str] = None  # ✅ NEW

    pickup_lat: float
    pickup_lng: float
    drop_lat: float
    drop_lng: float

    pickup_address: Optional[str] = None
    drop_address: Optional[str] = None

    vehicle_type: str
    scheduled_at: Optional[datetime] = None
    fare_estimate: Optional[float] = None
    fare_final: Optional[float] = None

    approved_by_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    rejected_by_id: Optional[int] = None
    rejected_at: Optional[datetime] = None

    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True
        from_attributes = True


    

    
# --------------------------- Favorites ---------------------------------------
class FavoriteCreate(BaseModel):
    user_id: int
    lat: float
    lng: float
    # Optional – backend will try to fill these smartly
    name: str | None = None
    address: str | None = None
    note: str | None = None

class FavoriteOut(BaseModel):
    id: int
    user_id: int
    name: str
    note: str | None
    address: str
    lat: float
    lng: float
    created_at: datetime

    class Config:
        from_attributes = True
# --------------------------- User Update ---------------------------
from typing import Optional

class UserUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None

    class Config:
        from_attributes = True
