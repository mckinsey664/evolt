from __future__ import annotations

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from markupsafe import Markup
from .database import Base, engine, get_db
from . import models
from .routers import auth, rides, drivers, favorites

from sqladmin import Admin, ModelView, action
from sqlalchemy import select
from sqlalchemy.orm import Session
from datetime import datetime
from sqladmin.forms import SelectField
from fastapi.responses import HTMLResponse, RedirectResponse



app = FastAPI(title="Taxi Backend (FastAPI)", version="0.7.0")

# ----------------------------------------------------
# 🔐 ADMIN LOGIN PROTECTION
# ----------------------------------------------------
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi import status
import secrets

security = HTTPBasic()

# 🔥 SET YOUR ADMIN CREDENTIALS HERE
ADMIN_EMAIL = "admin@evolt.com"
ADMIN_PASSWORD = "Evolt@app2026"


def verify_admin(credentials: HTTPBasicCredentials):
    correct_email = secrets.compare_digest(credentials.username, ADMIN_EMAIL)
    correct_password = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)

    if not (correct_email and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

# ----------------------------------------------------
# Middleware
# ----------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Development mode
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ----------------------------------------------------
# 🔒 Protect /admin routes
# ----------------------------------------------------
@app.middleware("http")
async def protect_admin(request, call_next):
    if request.url.path.startswith("/admin"):
        credentials = await security(request)
        verify_admin(credentials)
    response = await call_next(request)
    return response

# ----------------------------------------------------
# Database Initialization
# ----------------------------------------------------
Base.metadata.create_all(bind=engine)


def seed_car_types():
    """Seed default car types if database is empty."""
    from .database import SessionLocal
    with SessionLocal() as db:
        exists = db.scalars(select(models.CarType).limit(1)).first()
        if not exists:
            db.add_all([
                models.CarType(name="economy", base_fare=2.0, per_km=0.7, per_min=0.2),
                models.CarType(name="premium", base_fare=3.5, per_km=1.0, per_min=0.35),
                models.CarType(name="suv", base_fare=4.0, per_km=1.2, per_min=0.4),
            ])
            db.commit()


seed_car_types()

# ----------------------------------------------------
# Routers
# ----------------------------------------------------
app.include_router(auth.router)
app.include_router(rides.router)
app.include_router(drivers.router)
app.include_router(favorites.router) 

# ----------------------------------------------------
# Extra GET routes for Admin UI buttons
# ----------------------------------------------------
# @app.get("/admin/approve/{ride_id}")
# def approve_via_admin(ride_id: int, db: Session = Depends(get_db)):
#     """Allow GET approval from admin buttons."""
#     ride = db.get(models.Ride, ride_id)
#     if not ride:
#         return {"error": "Ride not found"}
#     ride.status = models.RideStatus.approved
#     ride.approved_at = datetime.utcnow()
#     ride.rejected_by_id = None
#     ride.rejected_at = None
#     db.commit()
#     return Markup(
#         "<body style='font-family:Arial;padding:40px;text-align:center;'>"
#         "<h2 style='color:green;'>✅ Ride Approved</h2>"
#         "<a href='/admin/ride/list' style='text-decoration:none;color:white;"
#         "background-color:#28a745;padding:10px 20px;border-radius:5px;'>Return to Rides</a>"
#         "</body>"
#     )


# @app.get("/admin/reject/{ride_id}")
# def reject_via_admin(ride_id: int, db: Session = Depends(get_db)):
#     """Allow GET rejection from admin buttons."""
#     ride = db.get(models.Ride, ride_id)
#     if not ride:
#         return {"error": "Ride not found"}
#     ride.status = models.RideStatus.rejected
#     ride.rejected_at = datetime.utcnow()
#     db.commit()
#     return Markup(
#         "<body style='font-family:Arial;padding:40px;text-align:center;'>"
#         "<h2 style='color:red;'>❌ Ride Rejected</h2>"
#         "<a href='/admin/ride/list' style='text-decoration:none;color:white;"
#         "background-color:#dc3545;padding:10px 20px;border-radius:5px;'>Return to Rides</a>"
#         "</body>"
#     )

@app.get("/admin/approve/{ride_id}")
def approve_via_admin(ride_id: int, db: Session = Depends(get_db)):
    ride = db.get(models.Ride, ride_id)
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")

    drivers = db.scalars(
        select(models.User)
        .where(
            models.User.role == models.UserRole.driver,
            models.User.name.isnot(None)
        )
        .order_by(models.User.name)
    ).all()

    options = "".join(
        f"<option value='{d.id}'>{d.name} — {d.phone}</option>"
        for d in drivers
    )

    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Assign Driver</title>
</head>
<body style="
    font-family: Arial, sans-serif;
    background: #f4f6f8;
    padding: 60px;
">
    <div style="
        max-width: 420px;
        margin: auto;
        background: white;
        padding: 30px;
        border-radius: 10px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.08);
    ">
        <h2 style="margin-bottom:20px;">🚗 Assign Driver</h2>
        <p style="color:#555;">Ride #{ride.id}</p>

        <form method="post" action="/admin/assign-driver/{ride.id}">
            <label style="font-weight:bold;">Select Driver</label><br><br>

            <select name="driver_id" required style="
                width:100%;
                padding:10px;
                border-radius:6px;
                border:1px solid #ccc;
            ">
                <option value="">— Choose a driver —</option>
                {options}
            </select>

            <br><br>

            <button type="submit" style="
                width:100%;
                background:#28a745;
                color:white;
                padding:12px;
                border:none;
                border-radius:6px;
                font-size:15px;
                cursor:pointer;
            ">
                ✅ Confirm & Approve Ride
            </button>

            <a href="/admin/ride/list" style="
                display:block;
                text-align:center;
                margin-top:15px;
                color:#777;
                text-decoration:none;
            ">
                Cancel
            </a>
        </form>
    </div>
</body>
</html>
"""
    return HTMLResponse(content=html)


from fastapi import Form
from fastapi.responses import RedirectResponse

from fastapi import Form

@app.post("/admin/assign-driver/{ride_id}")
def assign_driver(
    ride_id: int,
    driver_id: int = Form(...),
    db: Session = Depends(get_db),
):
    ride = db.get(models.Ride, ride_id)
    driver = db.get(models.User, driver_id)

    if not ride or not driver:
        raise HTTPException(status_code=404, detail="Ride or driver not found")

    if driver.role != models.UserRole.driver:
        raise HTTPException(status_code=400, detail="Selected user is not a driver")

    ride.driver_id = driver.id
    ride.status = models.RideStatus.approved
    ride.approved_at = datetime.utcnow()
    ride.rejected_at = None
    ride.rejected_by_id = None

    db.commit()

    return RedirectResponse("/admin/ride/list", status_code=303)




@app.get("/admin/reject/{ride_id}")
def reject_via_admin(ride_id: int, db: Session = Depends(get_db)):
    ride = db.get(models.Ride, ride_id)
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")

    ride.status = models.RideStatus.rejected
    ride.rejected_at = datetime.utcnow()
    ride.driver_id = None

    db.commit()

    return RedirectResponse(
        url="/admin/ride/list",
        status_code=303
    )


# ----------------------------------------------------
# Ride History (Frontend History Screen)
# ----------------------------------------------------
@app.get("/rides/history/{user_id}")
def get_ride_history(user_id: int, db: Session = Depends(get_db)):
    """
    Returns all rides for a given user (Pending, Approved, Rejected, Completed)
    for the Flutter History screen.
    Includes human-readable pickup_address & drop_address keys.
    """
    rides = db.scalars(
        select(models.Ride)
        .where(models.Ride.rider_id == user_id)
        .order_by(models.Ride.created_at.desc())
    ).all()

    results = []
    for r in rides:
        pick_addr = r.pickup_address or f"({r.pickup_lat:.4f}, {r.pickup_lng:.4f})"
        drop_addr = r.drop_address or f"({r.drop_lat:.4f}, {r.drop_lng:.4f})"

        results.append({
            "id": r.id,
            "pickup": f"({r.pickup_lat:.4f}, {r.pickup_lng:.4f})",
            "dropoff": f"({r.drop_lat:.4f}, {r.drop_lng:.4f})",
            "pickup_address": pick_addr,
            "drop_address": drop_addr,
            "status": r.status.value.capitalize() if r.status else "Pending",
            "vehicle_type": r.vehicle_type or "Unknown",
            "fare": round(float(r.fare_estimate or 0), 2),
            "notes": r.notes or "",
            "date": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "Unknown",
        })
    return results


# ----------------------------------------------------
# SQLAdmin Models
# ----------------------------------------------------
from passlib.hash import bcrypt
from sqladmin import ModelView
from app import models

class UserAdmin(ModelView, model=models.User):
    name = "User"
    name_plural = "Users"
    icon = "fa fa-user"

    column_list = [
        models.User.id,
        models.User.email,
        models.User.phone,
        models.User.name,
        models.User.role,
        models.User.created_at,
    ]

    

    # ✅ Admin sets PLAIN password here
    form_columns = [
        models.User.email,
        models.User.phone,
        models.User.name,
        models.User.role,
        models.User.password_hash,
    ]

    form_widget_args = {
        "password_hash": {
            "type": "password",
            "placeholder": "Set / change password",
        }
    }

    # ✅ MUST be async
    async def on_model_change(self, data, model, is_created, request):
        """
        SQLAdmin lifecycle hook (ASYNC REQUIRED)
        """

        # 🔐 Hash password if admin typed plain text
        if model.password_hash and not model.password_hash.startswith("$2"):
            model.password_hash = bcrypt.hash(model.password_hash)

        # 🚗 Auto-create driver profile when role becomes driver
        if model.role == models.UserRole.driver and not model.driver_profile:
            model.driver_profile = models.DriverProfile(
                status=models.DriverStatus.approved
            )



class DriverProfileAdmin(ModelView, model=models.DriverProfile):
    column_list = [
        models.DriverProfile.id,
        models.DriverProfile.user_id,
        models.DriverProfile.online,
        models.DriverProfile.status,
        models.DriverProfile.last_seen,
    ]
    name = "Driver Profile"
    name_plural = "Driver Profiles"
    icon = "fa fa-id-badge"


class CarTypeAdmin(ModelView, model=models.CarType):
    column_list = [
        models.CarType.id,
        models.CarType.name,
        models.CarType.base_fare,
        models.CarType.per_km,
        models.CarType.per_min,
        models.CarType.is_active,
        models.CarType.created_at,
    ]
    form_columns = [
        models.CarType.name,
        models.CarType.base_fare,
        models.CarType.per_km,
        models.CarType.per_min,
        models.CarType.is_active,
    ]
    name = "Car Type"
    name_plural = "Car Types"
    icon = "fa fa-car"


from zoneinfo import ZoneInfo

from zoneinfo import ZoneInfo

from zoneinfo import ZoneInfo
from datetime import timezone

def format_datetime_dual(dt: datetime | None, convert_from_utc: bool = False):
    if not dt:
        return "-"

    beirut_tz = ZoneInfo("Asia/Beirut")

    if convert_from_utc:
        # Force treat stored value as UTC
        dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(beirut_tz)

    return Markup(
        f"<div>"
        f"<div>{dt.strftime('%Y-%m-%d %H:%M:%S')}</div>"
        f"<div style='font-size:12px;color:#666;'>"
        f"{dt.strftime('%A %B %d, %Y at %-I:%M %p')}"
        f"</div>"
        f"</div>"
    )









# ----------------------------------------------------
# RideAdmin — simplified & cleaned display
# ----------------------------------------------------
class RideAdmin(ModelView, model=models.Ride):
    name = "Ride"
    name_plural = "Rides"
    icon = "fa fa-taxi"

    column_list = [
        models.Ride.id,
        models.Ride.status,
        models.Ride.vehicle_type,
        models.Ride.rider_id,
        models.Ride.driver_id,
        models.Ride.pickup_address,
        models.Ride.drop_address,
        models.Ride.fare_estimate,
        models.Ride.distance_km,
        models.Ride.duration_min,
        models.Ride.scheduled_at,
        models.Ride.created_at,
    ]

    # ✅ Clean, no 'From/To/Pinned' — just pure address text
    column_formatters = {
    models.Ride.status: lambda m, a: Markup(
        f"<div style='display:flex;align-items:center;gap:8px;'>"
        f"<span style='color:{'green' if m.status == models.RideStatus.approved else 'red' if m.status == models.RideStatus.rejected else 'orange'};"
        f"font-weight:bold;text-transform:capitalize;'>{m.status.value}</span>"
        f"<a href='/admin/approve/{m.id}' class='btn btn-success btn-sm' style='padding:3px 10px;'>Approve</a>"
        f"<a href='/admin/reject/{m.id}' class='btn btn-danger btn-sm' style='padding:3px 10px;'>Reject</a>"
        f"</div>"
    ),

    models.Ride.pickup_address: lambda m, a: Markup(
        f"<div style='line-height:1.4;'>{m.pickup_address or f'({m.pickup_lat:.4f}, {m.pickup_lng:.4f})'}</div>"
    ),

    models.Ride.drop_address: lambda m, a: Markup(
        f"<div style='line-height:1.4;'>{m.drop_address or f'({m.drop_lat:.4f}, {m.drop_lng:.4f})'}</div>"
    ),

    # ✅ NEW — formatted dates
    models.Ride.created_at: lambda m, a: format_datetime_dual(m.created_at, convert_from_utc=True),
    models.Ride.scheduled_at: lambda m, a: format_datetime_dual(m.scheduled_at, convert_from_utc=False),

}

    @action(name="approve_bulk", label="Approve Ride", confirmation_message="Approve selected ride(s)?")
    def approve_bulk(self, objs):
        with self.session as db:
            for r in objs:
                r.status = models.RideStatus.approved
                if not r.approved_at:
                    r.approved_at = datetime.utcnow()
                r.rejected_by_id = None
                r.rejected_at = None
            db.commit()

    @action(name="reject_bulk", label="Reject Ride", confirmation_message="Reject selected ride(s)?")
    def reject_bulk(self, objs):
        with self.session as db:
            for r in objs:
                r.status = models.RideStatus.rejected
                if not r.rejected_at:
                    r.rejected_at = datetime.utcnow()
            db.commit()


# ----------------------------------------------------
# SQLAdmin App Setup
# ----------------------------------------------------
admin = Admin(app, engine)
admin.add_view(UserAdmin)
admin.add_view(DriverProfileAdmin)
admin.add_view(CarTypeAdmin)
admin.add_view(RideAdmin)


# ----------------------------------------------------
# Root Endpoint
# ----------------------------------------------------
@app.get("/")
def root():
    return {
        "ok": True,
        "service": "taxi-backend",
        "docs": "/docs",
        "admin": "/admin",
    }
