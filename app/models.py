from __future__ import annotations
from datetime import datetime, date
from enum import Enum
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Date, Enum as SAEnum,
    ForeignKey, Boolean, Text
)
from sqlalchemy.orm import relationship
from .database import Base

# ---------------------------
# Enums
# ---------------------------
class UserRole(str, Enum):
    rider = "rider"
    driver = "driver"
    admin = "admin"

class DriverStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"

class RideStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    assigned = "assigned"
    arriving = "arriving"
    in_progress = "in_progress"
    completed = "completed"
    canceled = "canceled"

# ---------------------------
# Tables
# ---------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String, unique=True, index=True, nullable=True)
    name = Column(String, nullable=True)
    email = Column(String, unique=True, index=True, nullable=True)
    password_hash = Column(String, nullable=False)

    # extra profile
    language = Column(String, default="EN")
    gender = Column(String, nullable=True)
    birthdate = Column(Date, nullable=True)
    address = Column(String, nullable=True)
    payment_method = Column(String, nullable=True)

    role = Column(SAEnum(UserRole), default=UserRole.rider, index=True)
    avatar_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    driver_profile = relationship(
        "DriverProfile", back_populates="user", uselist=False,
        cascade="all, delete-orphan", passive_deletes=True
    )

    rides_as_rider = relationship(
        "Ride", primaryjoin="User.id==Ride.rider_id",
        cascade="all, delete-orphan", passive_deletes=True,
    )

    rides_as_driver = relationship(
        "Ride", primaryjoin="User.id==Ride.driver_id", passive_deletes=True,
    )
    favorites = relationship("Favorite", back_populates="user", cascade="all, delete")



class DriverProfile(Base):
    __tablename__ = "driver_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    car_model = Column(String, nullable=True)
    car_color = Column(String, nullable=True)
    plate = Column(String, nullable=True)
    license_number = Column(String, nullable=True)
    vehicle_year = Column(Integer, nullable=True)
    car_type_id = Column(Integer, ForeignKey("car_types.id"), nullable=True)
    status = Column(SAEnum(DriverStatus), default=DriverStatus.pending)
    online = Column(Boolean, default=False)
    last_lat = Column(Float, nullable=True)
    last_lng = Column(Float, nullable=True)
    last_seen = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="driver_profile", lazy="selectin")
    car_type = relationship("CarType", lazy="joined")


class CarType(Base):
    __tablename__ = "car_types"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    base_fare = Column(Float, default=2.0)
    per_km = Column(Float, default=0.7)
    per_min = Column(Float, default=0.2)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Ride(Base):
    __tablename__ = "rides"

    id = Column(Integer, primary_key=True, index=True)
    rider_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    driver_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    pickup_lat = Column(Float, nullable=False)
    pickup_lng = Column(Float, nullable=False)
    drop_lat = Column(Float, nullable=False)
    drop_lng = Column(Float, nullable=False)

    # ✅ Human-readable addresses
    pickup_address = Column(String, nullable=True)
    drop_address = Column(String, nullable=True)

    vehicle_type = Column(String, default="economy")
    scheduled_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

    status = Column(SAEnum(RideStatus), default=RideStatus.pending, index=True)
    fare_estimate = Column(Float, nullable=True)
    fare_final = Column(Float, nullable=True)
    distance_km = Column(Float, nullable=True)
    duration_min = Column(Float, nullable=True)

    approved_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejected_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    rejected_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship

# ...

class Favorite(Base):
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(100))
    note = Column(String(255))
    address = Column(String(255))
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="favorites")

