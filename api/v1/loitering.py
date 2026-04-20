from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from models.base import get_db
from models.loitering import AreaLoitering, AlarmLoitering
from core.loitering.detector import loitering_detector
from core.loitering.video_processor import loitering_processor


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
    status: Optional[int] = None,
    limit: Optional[int] = None,
    db: Session = Depends(get_db)
):
    query = db.query(AlarmLoitering)
    
    if area_id:
        query = query.filter(AlarmLoitering.content.contains(f'"area_id": "{area_id}"'))
    if start_time:
        query = query.filter(AlarmLoitering.alarm_time >= start_time)
    if end_time:
        query = query.filter(AlarmLoitering.alarm_time <= end_time)
    if status is not None:
        query = query.filter(AlarmLoitering.status == status)
    
    query = query.order_by(AlarmLoitering.alarm_time.desc())
    
    if limit:
        query = query.limit(limit)
    
    alarms = query.all()
    
    result = []
    for a in alarms:
        result.append({
            "id": a.id,
            "alarm_time": a.alarm_time.isoformat() if a.alarm_time else None,
            "event_id": a.event_id,
            "alarm_type": a.alarm_type,
            "content": a.content,
            "source_type": a.source_type,
            "source_id": a.source_id,
            "status": a.status
        })
    return {"alarms": result}


@router.get("/alarm/stats")
async def get_alarm_stats(db: Session = Depends(get_db)):
    """获取告警统计（未处理/已处理数量）"""
    unprocessed_count = db.query(AlarmLoitering).filter(AlarmLoitering.status == 0).count()
    processed_count = db.query(AlarmLoitering).filter(AlarmLoitering.status == 1).count()
    
    return {
        "unprocessed": unprocessed_count,
        "processed": processed_count,
        "total": unprocessed_count + processed_count
    }


class AlarmStatusUpdate(BaseModel):
    status: int


@router.post("/alarm/update/{alarm_id}")
async def update_alarm_status(alarm_id: int, update: AlarmStatusUpdate, db: Session = Depends(get_db)):
    """更新告警状态"""
    alarm = db.query(AlarmLoitering).filter(AlarmLoitering.id == alarm_id).first()
    if not alarm:
        raise HTTPException(status_code=404, detail="告警不存在")
    
    alarm.status = update.status
    db.commit()
    
    return {"message": "告警状态更新成功", "alarm_id": alarm_id, "status": update.status}


class BatchUpdateRequest(BaseModel):
    alarm_ids: list
    status: int


@router.post("/alarm/batch-update")
async def batch_update_alarm_status(request: BatchUpdateRequest, db: Session = Depends(get_db)):
    """批量更新告警状态"""
    updated_count = 0
    for alarm_id in request.alarm_ids:
        alarm = db.query(AlarmLoitering).filter(AlarmLoitering.id == alarm_id).first()
        if alarm:
            alarm.status = request.status
            updated_count += 1
    
    db.commit()
    
    return {"message": f"成功更新 {updated_count} 条告警状态", "updated_count": updated_count}


class BatchDeleteRequest(BaseModel):
    alarm_ids: list


@router.post("/alarm/batch-delete")
async def batch_delete_alarms(request: BatchDeleteRequest, db: Session = Depends(get_db)):
    """批量删除告警"""
    deleted_count = 0
    for alarm_id in request.alarm_ids:
        alarm = db.query(AlarmLoitering).filter(AlarmLoitering.id == alarm_id).first()
        if alarm:
            db.delete(alarm)
            deleted_count += 1
    
    db.commit()
    
    return {"message": f"成功删除 {deleted_count} 条告警", "deleted_count": deleted_count}


@router.delete("/alarm/{alarm_id}")
async def delete_alarm(alarm_id: int, db: Session = Depends(get_db)):
    """删除单条告警"""
    alarm = db.query(AlarmLoitering).filter(AlarmLoitering.id == alarm_id).first()
    if not alarm:
        raise HTTPException(status_code=404, detail="告警不存在")
    
    db.delete(alarm)
    db.commit()
    
    return {"message": "告警删除成功", "alarm_id": alarm_id}


@router.get("/status")
async def get_status():
    """获取检测状态"""
    return {
        "is_running": loitering_processor.is_running,
        "source_type": loitering_processor.current_source_type,
        "source_id": loitering_processor.current_source_id,
        "alert_count": len(loitering_processor.alarm_history) if hasattr(loitering_processor, 'alarm_history') else 0,
        "areas_count": len(loitering_detector.areas) if hasattr(loitering_detector, 'areas') else 0
    }


@router.post("/source/switch")
async def switch_source(source_type: str, source_id: str, device_id: Optional[int] = None):
    """切换输入源"""
    success = loitering_processor.switch_source(source_type, source_id, device_id)
    if success:
        return {"message": "输入源切换成功", "source_type": source_type, "source_id": source_id}
    else:
        return {"error": "输入源切换失败，请检查视频源是否可用"}


@router.post("/start")
async def start_detection(source_id: str):
    """启动徘徊检测"""
    if loitering_processor.is_running:
        return {"error": "检测已在运行中，请先停止"}
    
    success = loitering_processor.start_detection(source_id)
    if success:
        return {"message": "徘徊检测已启动", "source_id": source_id}
    else:
        return {"error": "启动失败，请检查视频源配置"}


@router.post("/stop")
async def stop_detection():
    """停止徘徊检测"""
    if not loitering_processor.is_running:
        return {"message": "检测未在运行"}
    
    loitering_processor.stop_detection()
    return {"message": "徘徊检测已停止"}
