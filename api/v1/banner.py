from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional


router = APIRouter(prefix="/banner", tags=["banner"])


@router.post("/start")
async def start_detection(source_id: str):
    return {"message": "banner detection started", "source_id": source_id}


@router.post("/stop")
async def stop_detection():
    return {"message": "banner detection stopped"}


@router.get("/alarm/list")
async def get_alarms():
    return {"message": "alarm list", "alarms": []}
