from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List


router = APIRouter(prefix="/source", tags=["source"])


class VideoSource(BaseModel):
    source_id: str
    source_name: str
    source_type: str
    device_id: Optional[int] = None
    source_addr: Optional[str] = None
    is_enable: bool = True


@router.post("/add")
async def add_source(source: VideoSource):
    return {"message": "add source", "source": source}


@router.post("/update")
async def update_source(source: VideoSource):
    return {"message": "update source", "source": source}


@router.post("/delete")
async def delete_source(source_id: str):
    return {"message": "delete source", "source_id": source_id}


@router.get("/list")
async def list_sources():
    return {"message": "list sources", "sources": []}


@router.post("/switch")
async def switch_source(source_type: str, source_id: str, device_id: Optional[int] = None, source_addr: Optional[str] = None):
    return {"message": "switch source", "source_type": source_type, "source_id": source_id}
