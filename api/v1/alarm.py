from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional


router = APIRouter(prefix="/alarm", tags=["alarm"])


@router.get("/list")
async def get_alarms(
    event_id: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    status: Optional[int] = None
):
    return {"message": "alarm list", "alarms": []}


@router.get("/statistics")
async def get_statistics(start_time: Optional[str] = None, end_time: Optional[str] = None):
    return {"message": "statistics", "data": {}}
