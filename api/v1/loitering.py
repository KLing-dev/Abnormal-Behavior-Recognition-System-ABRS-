from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional


router = APIRouter(prefix="/loitering", tags=["loitering"])


class AreaInfo(BaseModel):
    area_id: str
    area_name: str
    coords: str
    threshold_min: int = 10


@router.post("/area/add")
async def add_area(area: AreaInfo):
    return {"message": "area added", "area": area}


@router.post("/area/update")
async def update_area(area_id: str, threshold_min: Optional[int] = None):
    return {"message": "area updated", "area_id": area_id}


@router.post("/area/delete")
async def delete_area(area_id: str):
    return {"message": "area deleted", "area_id": area_id}


@router.get("/area/query")
async def query_areas(area_id: Optional[str] = None):
    return {"message": "area list", "areas": []}


@router.post("/source/switch")
async def switch_source(source_type: str, source_id: str, device_id: Optional[int] = None):
    return {"message": "source switched", "source_type": source_type, "source_id": source_id}


@router.post("/start")
async def start_detection(source_id: str):
    return {"message": "loitering detection started", "source_id": source_id}


@router.post("/stop")
async def stop_detection():
    return {"message": "loitering detection stopped"}


@router.get("/alarm/list")
async def get_alarms(area_id: Optional[str] = None, start_time: Optional[str] = None, end_time: Optional[str] = None):
    return {"message": "alarm list", "alarms": []}
