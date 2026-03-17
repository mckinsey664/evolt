from __future__ import annotations
import os, requests
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from sqlalchemy import select
from ..database import get_db
from .. import models, schemas
from ..services.dispatch import haversine
from ..services.dispatch import get_route_distance_duration  # ✅ import our new helper
from ..services.dispatch import get_route_with_polyline
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta




router = APIRouter(prefix="/rides", tags=["rides"])

# --------------------------
# Reverse Geocode Helper
# --------------------------
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "AIzaSyCPaZmolsO-km8YFLD6CPPFfSCH4rAb58A")

def reverse_geocode(lat: float, lng: float, typed_name: str | None = None) -> str:
    """
    Returns the most readable and accurate place name:
    - If the marker hits an official Google Place → use that name + area
    - If it's 'My current location' → full formatted address
    - If typed manually → keep typed name + append area
    - If unknown → fallback to readable short address
    """
    try:
        base = f"{lat},{lng}"

        # 1️⃣ My current location → full formatted address
        if typed_name and typed_name.lower().strip() == "my current location":
            geo_url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={base}&key={GOOGLE_MAPS_API_KEY}"
            resp = requests.get(geo_url, timeout=5).json()
            if resp.get("results"):
                return resp["results"][0].get("formatted_address", f"({lat:.4f}, {lng:.4f})")
            return f"({lat:.4f}, {lng:.4f})"

        # 2️⃣ Check if there’s a *known Google Maps place* exactly at that point
        place_url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={base}&radius=10&key={GOOGLE_MAPS_API_KEY}"
        place_resp = requests.get(place_url, timeout=5).json()

        known_name = None
        area_name = None
        if place_resp.get("results"):
            for p in place_resp["results"]:
                name = p.get("name")
                if name and not name.lower().startswith("unnamed"):
                    known_name = name
                    area_name = p.get("vicinity", "")
                    break

        # 3️⃣ Get readable formatted address (city/locality)
        geo_url = (
            f"https://maps.googleapis.com/maps/api/geocode/json"
            f"?latlng={base}&result_type=locality|plus_code|political"
            f"&key={GOOGLE_MAPS_API_KEY}"
        )
        geo_resp = requests.get(geo_url, timeout=5).json()
        readable_addr = ""
        if geo_resp.get("results"):
            addr = geo_resp["results"][0].get("formatted_address", "")
            parts = [p.strip() for p in addr.split(",")]
            if len(parts) > 2:
                readable_addr = ", ".join(parts[-2:])
            else:
                readable_addr = addr

        # 4️⃣ Combine based on available info
        if known_name and readable_addr:
            return f"{known_name}, {readable_addr}"
        if typed_name:
            return f"{typed_name}, {readable_addr or area_name or ''}".strip(", ")
        if readable_addr:
            return readable_addr
        if known_name:
            return known_name

        return f"Near ({lat:.4f}, {lng:.4f})"

    except Exception as e:
        print("Reverse geocoding error:", e)
        return f"({lat:.4f}, {lng:.4f})"




# --------------------------
# Fare Helper
# --------------------------
def estimate_fare(ct: models.CarType, km: float, minutes: float) -> float:
    return round((ct.base_fare or 0) + (ct.per_km or 0) * km + (ct.per_min or 0) * minutes, 2)


# --------------------------
# Admin Validation
# --------------------------
def require_admin(db: Session, admin_id: int | None):
    if not admin_id:
        raise HTTPException(status_code=401, detail="Missing X-Admin-Id header")
    admin = db.get(models.User, admin_id)
    if not admin or admin.role != models.UserRole.admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return admin


# --------------------------
# Endpoints
# --------------------------
@router.get("/car-types", response_model=list[schemas.CarTypeOut])
def list_car_types(db: Session = Depends(get_db)):
    return db.scalars(select(models.CarType).where(models.CarType.is_active == True)).all()


# ✅ Fixed & improved request endpoint
@router.post("/request", response_model=schemas.RideOut)
def request_ride(payload: schemas.RideRequest, db: Session = Depends(get_db)):
    rider = db.get(models.User, payload.rider_id)
    if not rider:
        raise HTTPException(status_code=404, detail="Rider not found")

    ct = db.scalars(
        select(models.CarType).where(
            models.CarType.name == payload.vehicle_type,
            models.CarType.is_active == True
        )
    ).first()
    if not ct:
        raise HTTPException(status_code=400, detail="Invalid vehicle type")

        # --------------------------------------------------
    # ⛔ REQUIRE DATE + TIME SELECTION
    # --------------------------------------------------
    if payload.scheduled_at is None:
        raise HTTPException(
            status_code=400,
            detail="Please select a pickup date and time."
        )
    
    beirut_tz = ZoneInfo("Asia/Beirut")

    scheduled_at = payload.scheduled_at

# If frontend sends naive datetime → assume it's Beirut local time
    if scheduled_at.tzinfo is None:
        scheduled_at = scheduled_at.replace(tzinfo=beirut_tz)
    else:
    # If timezone exists → convert to Beirut properly
        scheduled_at = scheduled_at.astimezone(beirut_tz)


    beirut_now = datetime.now(beirut_tz)
    min_allowed_time = beirut_now + timedelta(minutes=20)

    if scheduled_at <= min_allowed_time:
        raise HTTPException(
            status_code=400,
            detail="Pickup time must be at least 20 minutes from now."
        )


    # ✅ Get accurate driving route from Google Maps
    km, minutes = get_route_distance_duration(
        payload.pickup_lat, payload.pickup_lng,
        payload.drop_lat, payload.drop_lng
    )

    estimate = estimate_fare(ct, km, minutes)

    # ✅ Use user-selected address from Flutter if provided
    # ✅ Use typed names if provided; fallback to reverse-geocoded nearest place
    pickup_address = reverse_geocode(payload.pickup_lat, payload.pickup_lng, payload.pickup_address)
    drop_address = reverse_geocode(payload.drop_lat, payload.drop_lng, payload.drop_address)



    ride = models.Ride(
        rider_id=rider.id,
        pickup_lat=payload.pickup_lat,
        pickup_lng=payload.pickup_lng,
        drop_lat=payload.drop_lat,
        drop_lng=payload.drop_lng,
        pickup_address=pickup_address,
        drop_address=drop_address,
        vehicle_type=ct.name,
        scheduled_at=payload.scheduled_at,
        notes=payload.notes,
        status=models.RideStatus.pending,
        fare_estimate=estimate,
        distance_km=round(km or 0, 2),
        duration_min=int(round(minutes or 0)),
    )

    db.add(ride)
    db.commit()
    db.refresh(ride)
    return ride

@router.get("/route")
def get_route(
    pickup_lat: float,
    pickup_lng: float,
    drop_lat: float,
    drop_lng: float,
):
    """
    Returns real driving route with polyline
    """
    return get_route_with_polyline(
        pickup_lat, pickup_lng,
        drop_lat, drop_lng
    )

@router.get("/{ride_id}", response_model=schemas.RideOut)
def get_ride(ride_id: int, db: Session = Depends(get_db)):
    ride = db.get(models.Ride, ride_id)
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    return ride


# 🕒 Rider Ride History
@router.get("/user/{rider_id}/rides", response_model=list[schemas.RideOut])
def user_ride_history(rider_id: int, db: Session = Depends(get_db)):
    """
    Return all rides requested by this rider (newest first),
    including readable pickup and dropoff addresses.
    """
    rides = (
        db.query(models.Ride)
        .filter(models.Ride.rider_id == rider_id)
        .order_by(models.Ride.created_at.desc())
        .all()
    )
    return rides

# 🚗 Driver — Assigned / In-Progress Rides
@router.get("/driver/{driver_id}/assigned", response_model=list[schemas.RideOut])
def driver_assigned_rides(driver_id: int, db: Session = Depends(get_db)):

    rides = (
        db.query(models.Ride)
        .filter(
            models.Ride.driver_id == driver_id,
            models.Ride.status.in_([
                models.RideStatus.approved,
                models.RideStatus.in_progress
            ])
        )
        .order_by(models.Ride.created_at.desc())
        .all()
    )

    result = []

    for r in rides:
        rider = db.get(models.User, r.rider_id)

        ride_dict = schemas.RideOut.model_validate(r).dict()

        ride_dict["rider_name"] = rider.name if rider else None
        ride_dict["rider_phone"] = rider.phone if rider else None

        result.append(ride_dict)

    return result



# ▶️ Driver opens ride → mark as in_progress
@router.post("/driver/{driver_id}/open/{ride_id}")
def driver_open_ride(driver_id: int, ride_id: int, db: Session = Depends(get_db)):
    ride = db.get(models.Ride, ride_id)

    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")

    if ride.driver_id != driver_id:
        raise HTTPException(status_code=403, detail="Not your ride")

    if ride.status == models.RideStatus.approved:
        ride.status = models.RideStatus.in_progress
        db.commit()

    return {"ok": True, "status": ride.status.value}

# ✅ Driver completes ride
@router.post("/driver/{driver_id}/complete/{ride_id}")
def complete_ride(driver_id: int, ride_id: int, db: Session = Depends(get_db)):
    ride = db.get(models.Ride, ride_id)

    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")

    if ride.driver_id != driver_id:
        raise HTTPException(status_code=403, detail="Not your ride")

    if ride.status != models.RideStatus.in_progress:
        raise HTTPException(status_code=400, detail="Ride is not in progress")

    ride.status = models.RideStatus.completed
    ride.fare_final = ride.fare_estimate
    db.commit()

    return {"ok": True, "status": "completed"}

@router.put("/{ride_id}", response_model=schemas.RideOut)
def update_ride(
    ride_id: int,
    payload: schemas.RideUpdate,
    rider_id: int,
    db: Session = Depends(get_db),
):
    ride = db.get(models.Ride, ride_id)

    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")

    if ride.rider_id != rider_id:
        raise HTTPException(status_code=403, detail="Not your ride")

    if ride.status != models.RideStatus.pending:
        raise HTTPException(status_code=400, detail="Only pending rides can be edited")

    # Update fields
    ride.pickup_lat = payload.pickup_lat
    ride.pickup_lng = payload.pickup_lng
    ride.drop_lat = payload.drop_lat
    ride.drop_lng = payload.drop_lng
    ride.scheduled_at = payload.scheduled_at

    ride.pickup_address = payload.pickup_address
    ride.drop_address = payload.drop_address

    db.commit()
    db.refresh(ride)

    return ride


@router.delete("/{ride_id}")
def delete_ride(
    ride_id: int,
    rider_id: int,
    db: Session = Depends(get_db),
):
    ride = db.get(models.Ride, ride_id)

    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")

    if ride.rider_id != rider_id:
        raise HTTPException(status_code=403, detail="Not your ride")

    if ride.status != models.RideStatus.pending:
        raise HTTPException(status_code=400, detail="Only pending rides can be deleted")

    db.delete(ride)
    db.commit()

    return {"ok": True}


@router.get("/driver/{driver_id}/history", response_model=list[schemas.RideOut])
def driver_ride_history(driver_id: int, db: Session = Depends(get_db)):

    rides = (
        db.query(models.Ride)
        .filter(models.Ride.driver_id == driver_id)
        .order_by(models.Ride.created_at.desc())
        .all()
    )

    result = []

    for r in rides:
        rider = db.get(models.User, r.rider_id)

        ride_dict = schemas.RideOut.model_validate(r).dict()

        ride_dict["rider_name"] = rider.name if rider else None
        ride_dict["rider_phone"] = rider.phone if rider else None

        result.append(ride_dict)

    return result

