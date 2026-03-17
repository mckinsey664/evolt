from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from passlib.hash import bcrypt
from app.database import get_db
from app import models, schemas

from twilio.rest import Client
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import re

load_dotenv()

router = APIRouter(tags=["auth"])

MAX_PASSWORD_LENGTH = 72


# ==================================================
# Twilio Setup
# ==================================================
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_VERIFY_SERVICE_SID = os.getenv("TWILIO_VERIFY_SERVICE_SID")

if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_VERIFY_SERVICE_SID:
    raise RuntimeError("Twilio environment variables are missing.")

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


# ==================================================
# PHONE NORMALIZER
# ==================================================
def normalize_phone(phone: str) -> str:
    phone = phone.strip()

    phone = phone.replace(" ", "")

    phone = re.sub(r"[^\d+]", "", phone)

    if not phone.startswith("+"):
        phone = "+" + phone

    return phone


# ==================================================
# REQUEST MODELS
# ==================================================

class SendOTPRequest(BaseModel):
    phone: str


class OTPVerifyRequest(BaseModel):
    name: str
    phone: str
    password: str
    role: str = "rider"
    code: str


# ==================================================
# 1️⃣ SEND OTP
# ==================================================
@router.post("/auth/send-otp")
def send_otp(data: SendOTPRequest, db: Session = Depends(get_db)):

    phone = normalize_phone(data.phone)

    print("Normalized phone:", phone)

    if not phone.startswith("+961"):
        return {
            "success": False,
            "message": "Phone must be Lebanese (+961XXXXXXXX)"
        }

    # CHECK IF PHONE EXISTS
    existing = db.query(models.User).filter(models.User.phone == phone).first()

    if existing:
        return {
            "success": False,
            "message": "Phone already registered. Please login."
        }

    try:

        verification = twilio_client.verify.v2.services(
            TWILIO_VERIFY_SERVICE_SID
        ).verifications.create(
            to=phone,
            channel="sms"
        )

        print("Twilio SID:", verification.sid)
        print("Twilio status:", verification.status)

        return {
            "success": True,
            "message": "OTP sent successfully"
        }

    except Exception as e:

        print("Twilio send error:", str(e))

        return {
            "success": False,
            "message": "Failed to send OTP"
        }


# ==================================================
# 2️⃣ VERIFY OTP + CREATE USER
# ==================================================
@router.post("/auth/verify-otp")
def verify_otp(data: OTPVerifyRequest, db: Session = Depends(get_db)):

    phone = normalize_phone(data.phone)

    if not phone.startswith("+961"):
        raise HTTPException(status_code=400, detail="Invalid Lebanese phone format")

    try:

        # Verify OTP with Twilio
        check = twilio_client.verify.v2.services(
            TWILIO_VERIFY_SERVICE_SID
        ).verification_checks.create(
            to=phone,
            code=data.code
        )

        print("Verification status:", check.status)

        if check.status != "approved":
            raise HTTPException(status_code=400, detail="Invalid OTP")

        # Check if user already exists
        user = db.query(models.User).filter(models.User.phone == phone).first()

        # If user does NOT exist → create user
        if not user:

            if not data.password:
                raise HTTPException(status_code=400, detail="Password required for new user")

            if len(data.password) > MAX_PASSWORD_LENGTH:
                raise HTTPException(status_code=400, detail="Password too long")

            hashed = bcrypt.hash(data.password[:MAX_PASSWORD_LENGTH])

            user = models.User(
                name=data.name,
                phone=phone,
                password_hash=hashed,
                role=models.UserRole(data.role),
            )

            db.add(user)
            db.commit()
            db.refresh(user)

        # If user exists → login directly

        return {
            "success": True,
            "message": "Login successful",
            "user_id": user.id,
            "name": user.name,
            "phone": user.phone,
            "role": user.role.value
        }

    except HTTPException:
        raise

    except Exception as e:
        print("Twilio verify error:", str(e))
        raise HTTPException(status_code=400, detail=str(e))


# ==================================================
# LOGIN
# ==================================================
@router.post("/auth/login")
def login(data: schemas.LoginRequest, db: Session = Depends(get_db)):

    phone = normalize_phone(data.phone)

    user = db.query(models.User).filter(models.User.phone == phone).first()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid phone or password")

    if not bcrypt.verify(data.password[:MAX_PASSWORD_LENGTH], user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid phone or password")

    return {
        "success": True,
        "user_id": user.id,
        "name": user.name,
        "phone": user.phone,
        "role": user.role.value
    }

# ==================================================
# DELETE ACCOUNT
# ==================================================
@router.delete("/auth/delete_user/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):

    user = db.query(models.User).filter(models.User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent deleting account if user has active rides
    active_ride = db.query(models.Ride).filter(
        models.Ride.rider_id == user_id,
        models.Ride.status.in_([
            models.RideStatus.pending,
            models.RideStatus.assigned,
            models.RideStatus.arriving,
            models.RideStatus.in_progress
        ])
    ).first()

    if active_ride:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete account while ride is active"
        )

    # Delete user (CASCADE will delete related data)
    db.delete(user)
    db.commit()

    return {
        "success": True,
        "message": "Account deleted successfully"
    }

# ===============================
# UPDATE USER PROFILE
# ===============================
@router.put("/auth/update_user/{user_id}")
def update_user(
    user_id: int,
    data: schemas.UserUpdate,
    db: Session = Depends(get_db)
):

    user = db.query(models.User).filter(models.User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # update name
    if data.name is not None:
        user.name = data.name

    
    

    db.commit()
    db.refresh(user)

    return {
        "id": user.id,
        "name": user.name,
        "phone": user.phone
    }