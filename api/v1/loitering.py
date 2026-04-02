from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from models.base import get_db
from models.loitering import AreaLoitering, AlarmLoitering


router = APIRouter(prefix="/loitering", tags=["loitering"])


class AreaInfo(BaseModel):
    area_id: str
    area_name: str
    coords: str
    threshold_min: int = 10


class AreaUpdateInfo(BaseModel):
    area_id: str
    area_name: Optional[str] = None
    coords: Optional[str] = None
    threshold_min: Optional[int] = None
    is_enable: Optional[int] = None


@router.post("/area/add")
async def add_area(area: AreaInfo, db: Session = Depends(get_db)):
    db_area = AreaLoitering(
        area_id=area.area_id,
        area_name=area.area_name,
        coords=area.coords,
        threshold_min=area.threshold_min,
        is_enable=1
    )
    db.add(db_area)
    db.commit()
    db.refresh(db_area)
    return {"message": "区域添加成功", "area_id": area.area_id}


@router.post("/area/update")
async def update_area(info: AreaUpdateInfo, db: Session = Depends(get_db)):
    db_area = db.query(AreaLoitering).filter(AreaLoitering.area_id == info.area_id).first()
    if not db_area:
        return {"error": "区域不存在", "area_id": info.area_id}
    
    if info.area_name:
        db_area.area_name = info.area_name
    if info.coords:
        db_area.coords = info.coords
    if info.threshold_min is not None:
        db_area.threshold_min = info.threshold_min
    if info.is_enable is not None:
        db_area.is_enable = info.is_enable
    
    db.commit()
    return {"message": "区域更新成功", "area_id": info.area_id}


@router.post("/area/delete")
async def delete_area(area_id: str, db: Session = Depends(get_db)):
    db_area = db.query(AreaLoitering).filter(AreaLoitering.area_id == area_id).first()
    if not db_area:
        return {"error": "区域不存在", "area_id": area_id}
    
    db.delete(db_area)
    db.commit()
    return {"message": "区域删除成功", "area_id": area_id}


@router.get("/area/query")
async def query_areas(area_id: Optional[str] = None, db: Session = Depends(get_db)):
    if area_id:
        areas = db.query(AreaLoitering).filter(AreaLoitering.area_id == area_id).all()
    else:
        areas = db.query(AreaLoitering).all()
    
    result = []
    for a in areas:
        result.append({
            "area_id": a.area_id,
            "area_name": a.area_name,
            "coords": a.coords,
            "threshold_min": a.threshold_min,
            "is_enable": a.is_enable,
            "create_time": a.create_time.isoformat() if a.create_time else None
        })
    return {"areas": result}


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
async def get_alarms(
    area_id: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(AlarmLoitering)
    
    if area_id:
        query = query.filter(AlarmLoitering.content.contains(f'"area_id": "{area_id}"'))
    if start_time:
        query = query.filter(AlarmLoitering.alarm_time >= start_time)
    if end_time:
        query = query.filter(AlarmLoitering.alarm_time <= end_time)
    
    alarms = query.order_by(AlarmLoitering.alarm_time.desc()).all()
    
    result = []
    for a in alarms:
        result.append({
            "alarm_time": a.alarm_time.isoformat() if a.alarm_time else None,
            "event_id": a.event_id,
            "alarm_type": a.alarm_type,
            "content": a.content,
            "source_type": a.source_type,
            "source_id": a.source_id,
            "status": a.status
        })
    return {"alarms": result}
