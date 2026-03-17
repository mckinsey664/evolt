from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from ..database import get_db
from .. import models

router = APIRouter(prefix="/favorites", tags=["favorites"])

# GET — All favorites for user
@router.get("/{user_id}")
def list_favorites(user_id: int, db: Session = Depends(get_db)):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    favorites = db.scalars(
        select(models.Favorite).where(models.Favorite.user_id == user_id)
    ).all()
    return [
        {
            "id": f.id,
            "name": f.name,
            "note": f.note,
            "address": f.address,
            "lat": f.lat,
            "lng": f.lng,
        }
        for f in favorites
    ]

# POST — Add new favorite
@router.post("")
def add_favorite(payload: dict, db: Session = Depends(get_db)):
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing user_id")

    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    fav = models.Favorite(
        user_id=user_id,
        name=payload.get("name"),
        note=payload.get("note"),
        address=payload.get("address"),
        lat=payload.get("lat"),
        lng=payload.get("lng"),
    )
    db.add(fav)
    db.commit()
    db.refresh(fav)
    return {
        "id": fav.id,
        "name": fav.name,
        "note": fav.note,
        "address": fav.address,
        "lat": fav.lat,
        "lng": fav.lng,
    }

# DELETE — Remove favorite
@router.delete("/{fav_id}")
def delete_favorite(fav_id: int, db: Session = Depends(get_db)):
    fav = db.get(models.Favorite, fav_id)
    if not fav:
        raise HTTPException(status_code=404, detail="Favorite not found")

    db.delete(fav)
    db.commit()
    return {"success": True, "message": "Favorite deleted"}
