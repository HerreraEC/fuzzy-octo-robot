"""
Announcement endpoints for the High School Management System API
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from datetime import datetime
from bson import ObjectId

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


class AnnouncementCreate(BaseModel):
    title: str
    message: str
    start_date: Optional[datetime] = None
    expiration_date: datetime


class AnnouncementUpdate(BaseModel):
    title: Optional[str] = None
    message: Optional[str] = None
    start_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None


def _format(ann: dict) -> dict:
    ann = dict(ann)
    ann["id"] = str(ann.pop("_id"))
    # Serialize datetimes to ISO strings
    for field in ("start_date", "expiration_date", "created_at"):
        if isinstance(ann.get(field), datetime):
            ann[field] = ann[field].isoformat()
    return ann


def _require_teacher(teacher_username: str):
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Authentication required")
    return teacher


@router.get("", response_model=List[Dict[str, Any]])
def get_active_announcements():
    """Get currently active announcements (public)"""
    now = datetime.utcnow()
    query = {
        "expiration_date": {"$gt": now},
        "$or": [
            {"start_date": None},
            {"start_date": {"$exists": False}},
            {"start_date": {"$lte": now}},
        ],
    }
    return [_format(a) for a in announcements_collection.find(query).sort("created_at", -1)]


@router.get("/all", response_model=List[Dict[str, Any]])
def get_all_announcements(teacher_username: str = Query(...)):
    """Get all announcements including expired ones (requires teacher auth)"""
    _require_teacher(teacher_username)
    return [_format(a) for a in announcements_collection.find().sort("created_at", -1)]


@router.post("", response_model=Dict[str, Any])
def create_announcement(
    announcement: AnnouncementCreate,
    teacher_username: str = Query(...),
):
    """Create a new announcement (requires teacher auth)"""
    _require_teacher(teacher_username)
    doc = {
        **announcement.model_dump(),
        "created_by": teacher_username,
        "created_at": datetime.utcnow(),
    }
    result = announcements_collection.insert_one(doc)
    created = announcements_collection.find_one({"_id": result.inserted_id})
    return _format(created)


@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(
    announcement_id: str,
    announcement: AnnouncementUpdate,
    teacher_username: str = Query(...),
):
    """Update an existing announcement (requires teacher auth)"""
    _require_teacher(teacher_username)

    try:
        oid = ObjectId(announcement_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")

    update_data = {k: v for k, v in announcement.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = announcements_collection.update_one({"_id": oid}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    updated = announcements_collection.find_one({"_id": oid})
    return _format(updated)


@router.delete("/{announcement_id}")
def delete_announcement(
    announcement_id: str,
    teacher_username: str = Query(...),
):
    """Delete an announcement (requires teacher auth)"""
    _require_teacher(teacher_username)

    try:
        oid = ObjectId(announcement_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")

    result = announcements_collection.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return {"message": "Announcement deleted successfully"}
