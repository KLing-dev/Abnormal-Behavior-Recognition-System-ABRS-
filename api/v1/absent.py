from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional


router = APIRouter(prefix="/absent", tags=["absent"])


class PersonInfo(BaseModel):
    person_id: str
    name: str
    post: str
    duty_period: str
    max_absent_min: int = 5
    face_img: Optional[str] = None


@router.post("/person/add")
async def add_person(person: PersonInfo):
    return {"message": "person added", "person": person}


@router.post("/person/update")
async def update_person(person_id: str, max_absent_min: Optional[int] = None):
    return {"message": "person updated", "person_id": person_id}


@router.post("/person/delete")
async def delete_person(person_id: str):
    return {"message": "person deleted", "person_id": person_id}


@router.get("/person/query")
async def query_persons(person_id: Optional[str] = None):
    return {"message": "person list", "persons": []}


@router.post("/source/switch")
async def switch_source(source_type: str, source_id: str, device_id: Optional[int] = None):
    return {"message": "source switched", "source_type": source_type, "source_id": source_id}


@router.post("/start")
async def start_detection(source_id: str):
    return {"message": "absent detection started", "source_id": source_id}


@router.post("/stop")
async def stop_detection():
    return {"message": "absent detection stopped"}


@router.get("/alarm/list")
async def get_alarms(person_id: Optional[str] = None, start_time: Optional[str] = None, end_time: Optional[str] = None):
    return {"message": "alarm list", "alarms": []}
