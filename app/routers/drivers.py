
from __future__ import annotations
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas

router = APIRouter(prefix="/drivers", tags=["drivers"])

@router.post("/{driver_id}/status")
def update_status(driver_id: int, payload: schemas.DriverStatusUpdate, db: Session = Depends(get_db)):
    user = db.get(models.User, driver_id)
    if not user or user.role != models.UserRole.driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    profile = user.driver_profile
    if not profile:
        profile = models.DriverProfile(user_id=user.id, status=models.DriverStatus.approved)
        db.add(profile); db.commit(); db.refresh(profile)
    profile.online = payload.online
    profile.last_seen = datetime.utcnow()
    db.commit()
    return {"ok": True, "online": profile.online}

@router.post("/{driver_id}/location")
def update_location(driver_id: int, payload: schemas.LocationUpdate, db: Session = Depends(get_db)):
    user = db.get(models.User, driver_id)
    if not user or user.role != models.UserRole.driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    profile = user.driver_profile
    if not profile:
        profile = models.DriverProfile(user_id=user.id, status=models.DriverStatus.approved)
        db.add(profile); db.commit(); db.refresh(profile)
    profile.last_lat = payload.lat
    profile.last_lng = payload.lng
    profile.last_seen = datetime.utcnow()
    db.commit()
    return {"ok": True}
