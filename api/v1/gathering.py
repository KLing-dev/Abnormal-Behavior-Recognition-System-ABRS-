from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict
from sqlalchemy.orm import Session
from models.base import get_db
from models.gathering import AreaGathering, AlarmGathering
from core.gathering.detector import gathering_detector
from core.gathering.video_processor import gathering_processor


router = APIRouter(prefix="/gathering", tags=["gathering"])


class LevelThresholds(BaseModel):
    light: int = 5
    medium: int = 10
    urgent: int = 20


class AreaInfo(BaseModel):
    area_id: str
    area_name: str
    coords: str
    level_thresholds: Optional[LevelThresholds] = None


class AreaUpdateInfo(BaseModel):
    area_id: str
    area_name: Optional[str] = None
    coords: Optional[str] = None
    level_thresholds: Optional[LevelThresholds] = None
    is_enable: Optional[int] = None


class StartDetectionInfo(BaseModel):
    source_type: str
    source_id: str
    source_addr: Optional[str] = None


@router.post("/area/add")
async def add_area(area: AreaInfo, db: Session = Depends(get_db)):
    level_thresholds_data = None
    if area.level_thresholds:
        level_thresholds_data = area.level_thresholds.model_dump()
    else:
        level_thresholds_data = {"light": 5, "medium": 10, "urgent": 20}
    
    db_area = AreaGathering(
        area_id=area.area_id,
        area_name=area.area_name,
        coords=area.coords,
        level_thresholds=level_thresholds_data,
        is_enable=1
    )
    db.add(db_area)
    db.commit()
    db.refresh(db_area)
    return {"message": "区域添加成功", "area_id": area.area_id}


@router.post("/area/update")
async def update_area(info: AreaUpdateInfo, db: Session = Depends(get_db)):
    db_area = db.query(AreaGathering).filter(AreaGathering.area_id == info.area_id).first()
    if not db_area:
        return {"error": "区域不存在", "area_id": info.area_id}
    
    if info.area_name:
        db_area.area_name = info.area_name
    if info.coords:
        db_area.coords = info.coords
    if info.level_thresholds:
        db_area.level_thresholds = info.level_thresholds.model_dump()
    if info.is_enable is not None:
        db_area.is_enable = info.is_enable
    
    db.commit()
    return {"message": "区域更新成功", "area_id": info.area_id}


@router.post("/area/delete")
async def delete_area(info: AreaUpdateInfo, db: Session = Depends(get_db)):
    db_area = db.query(AreaGathering).filter(AreaGathering.area_id == info.area_id).first()
    if not db_area:
        return {"error": "区域不存在", "area_id": info.area_id}

    db.delete(db_area)
    db.commit()
    return {"message": "区域删除成功", "area_id": info.area_id}


@router.get("/area/query")
async def query_areas(area_id: Optional[str] = None, db: Session = Depends(get_db)):
    if area_id:
        areas = db.query(AreaGathering).filter(AreaGathering.area_id == area_id).all()
    else:
        areas = db.query(AreaGathering).all()
    
    result = []
    for a in areas:
        result.append({
            "area_id": a.area_id,
            "area_name": a.area_name,
            "coords": a.coords,
            "level_thresholds": a.level_thresholds,
            "is_enable": a.is_enable,
            "create_time": a.create_time.isoformat() if a.create_time else None
        })
    return {"areas": result}


@router.post("/source/switch")
async def switch_source(source_type: str, source_id: str, device_id: Optional[int] = None):
    return {"message": "source switched", "source_type": source_type, "source_id": source_id}


@router.post("/start")
async def start_detection(info: StartDetectionInfo):
    return {"message": "gathering detection started", "source_id": info.source_id, "source_type": info.source_type, "source_addr": info.source_addr}


@router.post("/stop")
async def stop_detection():
    return {"message": "gathering detection stopped"}


@router.get("/alarm/list")
async def get_alarms(
    area_id: Optional[str] = None,
    level: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    status: Optional[int] = None,
    limit: Optional[int] = None,
    db: Session = Depends(get_db)
):
    query = db.query(AlarmGathering)
    
    if area_id:
        query = query.filter(AlarmGathering.content.contains(f'"area_id": "{area_id}"'))
    if start_time:
        query = query.filter(AlarmGathering.alarm_time >= start_time)
    if end_time:
        query = query.filter(AlarmGathering.alarm_time <= end_time)
    if status is not None:
        query = query.filter(AlarmGathering.status == status)
    
    query = query.order_by(AlarmGathering.alarm_time.desc())
    
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
    unprocessed_count = db.query(AlarmGathering).filter(AlarmGathering.status == 0).count()
    processed_count = db.query(AlarmGathering).filter(AlarmGathering.status == 1).count()
    
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
    alarm = db.query(AlarmGathering).filter(AlarmGathering.id == alarm_id).first()
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
        alarm = db.query(AlarmGathering).filter(AlarmGathering.id == alarm_id).first()
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
        alarm = db.query(AlarmGathering).filter(AlarmGathering.id == alarm_id).first()
        if alarm:
            db.delete(alarm)
            deleted_count += 1
    
    db.commit()
    
    return {"message": f"成功删除 {deleted_count} 条告警", "deleted_count": deleted_count}


@router.delete("/alarm/{alarm_id}")
async def delete_alarm(alarm_id: int, db: Session = Depends(get_db)):
    """删除单条告警"""
    alarm = db.query(AlarmGathering).filter(AlarmGathering.id == alarm_id).first()
    if not alarm:
        raise HTTPException(status_code=404, detail="告警不存在")
    
    db.delete(alarm)
    db.commit()
    
    return {"message": "告警删除成功", "alarm_id": alarm_id}


@router.get("/status")
async def get_status():
    """获取检测状态"""
    return {
        "is_running": gathering_processor.is_running,
        "source_type": gathering_processor.current_source_type,
        "source_id": gathering_processor.current_source_id,
        "alert_count": len(gathering_processor.alarm_history) if hasattr(gathering_processor, 'alarm_history') else 0,
        "areas_count": len(gathering_detector.areas) if hasattr(gathering_detector, 'areas') else 0
    }


@router.post("/source/switch")
async def switch_source(source_type: str, source_id: str, device_id: Optional[int] = None):
    """切换输入源"""
    success = gathering_processor.switch_source(source_type, source_id, device_id)
    if success:
        return {"message": "输入源切换成功", "source_type": source_type, "source_id": source_id}
    else:
        return {"error": "输入源切换失败，请检查视频源是否可用"}


@router.post("/start")
async def start_detection(info: StartDetectionInfo):
    """启动聚集检测"""
    if gathering_processor.is_running:
        return {"error": "检测已在运行中，请先停止"}
    
    success = gathering_processor.start_detection(info.source_id)
    if success:
        return {"message": "聚集检测已启动", "source_id": info.source_id}
    else:
        return {"error": "启动失败，请检查视频源配置"}


@router.post("/stop")
async def stop_detection():
    """停止聚集检测"""
    if not gathering_processor.is_running:
        return {"message": "检测未在运行"}
    
    gathering_processor.stop_detection()
    return {"message": "聚集检测已停止"}
