from __future__ import annotations
import os, requests
from math import radians, sin, cos, asin, sqrt
from sqlalchemy.orm import Session
from .. import models

# Google Maps API key
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "AIzaSyCPaZmolsO-km8YFLD6CPPFfSCH4rAb58A")

# ------------------------------
# Haversine (fallback)
# ------------------------------
def haversine(lat1, lon1, lat2, lon2) -> float:
    """Return straight-line distance in KM (fallback if Google API fails)."""
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return R * c


# ------------------------------
# Accurate Route Distance & Duration
# ------------------------------
def get_route_distance_duration(lat1, lon1, lat2, lon2):
    """
    Fetch real driving distance (km) and duration (minutes)
    using Google Distance Matrix API.
    Falls back to Haversine if API fails.
    """
    try:
        url = (
            "https://maps.googleapis.com/maps/api/distancematrix/json"
            f"?origins={lat1},{lon1}"
            f"&destinations={lat2},{lon2}"
            "&mode=driving"
            "&units=metric"
            "&traffic_model=best_guess"
            "&departure_time=now"
            f"&key={GOOGLE_MAPS_API_KEY}"
        )
        res = requests.get(url, timeout=6).json()

        if res.get("status") == "OK":
            element = res["rows"][0]["elements"][0]
            if element.get("status") == "OK":
                distance_km = element["distance"]["value"] / 1000.0
                duration_min = element["duration"]["value"] / 60.0
                return round(distance_km, 2), round(duration_min, 1)

        # fallback
        dist = haversine(lat1, lon1, lat2, lon2)
        return round(dist, 2), round(dist * 3, 1)

    except Exception as e:
        print("⚠️ Distance API error:", e)
        dist = haversine(lat1, lon1, lat2, lon2)
        return round(dist, 2), round(dist * 3, 1)


# ------------------------------
# Find Nearest Driver (unchanged)
# ------------------------------
def find_nearest_driver(db: Session, lat: float, lng: float, radius_km: float = 8.0):
    """Simple nearest-online-approved driver search."""
    q = (
        db.query(models.DriverProfile)
        .filter(models.DriverProfile.online == True)
        .filter(models.DriverProfile.status == models.DriverStatus.approved)
        .filter(models.DriverProfile.last_lat.isnot(None))
        .filter(models.DriverProfile.last_lng.isnot(None))
    )
    best = None
    best_dist = 1e9
    for prof in q:
        dist = haversine(lat, lng, prof.last_lat, prof.last_lng)
        if dist < best_dist and dist <= radius_km:
            best = prof
            best_dist = dist
    return best

# ------------------------------
# Route with Polyline (Directions API)
# ------------------------------
def get_route_with_polyline(lat1, lon1, lat2, lon2):
    """
    Returns:
    - distance_km
    - duration_min
    - encoded_polyline
    """
    try:
        url = (
            "https://maps.googleapis.com/maps/api/directions/json"
            f"?origin={lat1},{lon1}"
            f"&destination={lat2},{lon2}"
            "&mode=driving"
            "&units=metric"
            f"&key={GOOGLE_MAPS_API_KEY}"
        )

        res = requests.get(url, timeout=6).json()

        if res.get("status") == "OK":
            route = res["routes"][0]
            leg = route["legs"][0]

            distance_km = leg["distance"]["value"] / 1000
            duration_min = leg["duration"]["value"] / 60
            polyline = route["overview_polyline"]["points"]

            return {
                "distance_km": round(distance_km, 2),
                "duration_min": round(duration_min, 1),
                "polyline": polyline,
            }

        # fallback (no polyline)
        dist = haversine(lat1, lon1, lat2, lon2)
        return {
            "distance_km": round(dist, 2),
            "duration_min": round(dist * 3, 1),
            "polyline": None,
        }

    except Exception as e:
        print("⚠️ Directions API error:", e)
        dist = haversine(lat1, lon1, lat2, lon2)
        return {
            "distance_km": round(dist, 2),
            "duration_min": round(dist * 3, 1),
            "polyline": None,
        }
