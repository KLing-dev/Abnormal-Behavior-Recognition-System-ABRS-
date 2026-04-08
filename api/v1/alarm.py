from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from models.base import get_db
from models.banner import AlarmBanner
from models.absent import AlarmAbsent
from models.loitering import AlarmLoitering
from models.gathering import AlarmGathering


router = APIRouter(prefix="/alarm", tags=["alarm"])


class AlarmMarkRequest(BaseModel):
    alarm_ids: List[str]


@router.get("/list")
async def get_alarms(
    event_id: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    status: Optional[int] = None,
    db: Session = Depends(get_db)
):
    return {"message": "alarm list", "alarms": []}


@router.get("/statistics")
async def get_statistics(start_time: Optional[str] = None, end_time: Optional[str] = None):
    return {"message": "statistics", "data": {}}


@router.get("/stats")
async def get_alarm_stats():
    return {
        "today_count": 0,
        "banner_count": 0,
        "absent_count": 0,
        "loitering_count": 0,
        "gathering_count": 0
    }


@router.get("/detail")
async def get_alarm_detail(alarm_id: str, db: Session = Depends(get_db)):
    """查询单条告警详情"""
    # 尝试从各模块告警表中查询
    alarm = None
    
    # 查询横幅告警
    alarm = db.query(AlarmBanner).filter(AlarmBanner.id == alarm_id).first()
    if alarm:
        return {
            "alarm_id": alarm_id,
            "alarm_time": alarm.alarm_time.isoformat() if alarm.alarm_time else None,
            "event_id": alarm.event_id,
            "alarm_type": alarm.alarm_type,
            "content": alarm.content,
            "source_type": alarm.source_type,
            "source_id": alarm.source_id,
            "status": alarm.status
        }
    
    # 查询离岗告警
    alarm = db.query(AlarmAbsent).filter(AlarmAbsent.id == alarm_id).first()
    if alarm:
        return {
            "alarm_id": alarm_id,
            "alarm_time": alarm.alarm_time.isoformat() if alarm.alarm_time else None,
            "event_id": alarm.event_id,
            "alarm_type": alarm.alarm_type,
            "content": alarm.content,
            "source_type": alarm.source_type,
            "source_id": alarm.source_id,
            "status": alarm.status
        }
    
    # 查询徘徊告警
    alarm = db.query(AlarmLoitering).filter(AlarmLoitering.id == alarm_id).first()
    if alarm:
        return {
            "alarm_id": alarm_id,
            "alarm_time": alarm.alarm_time.isoformat() if alarm.alarm_time else None,
            "event_id": alarm.event_id,
            "alarm_type": alarm.alarm_type,
            "content": alarm.content,
            "source_type": alarm.source_type,
            "source_id": alarm.source_id,
            "status": alarm.status
        }
    
    # 查询聚集告警
    alarm = db.query(AlarmGathering).filter(AlarmGathering.id == alarm_id).first()
    if alarm:
        return {
            "alarm_id": alarm_id,
            "alarm_time": alarm.alarm_time.isoformat() if alarm.alarm_time else None,
            "event_id": alarm.event_id,
            "alarm_type": alarm.alarm_type,
            "content": alarm.content,
            "source_type": alarm.source_type,
            "source_id": alarm.source_id,
            "status": alarm.status
        }
    
    return {"error": "告警不存在", "alarm_id": alarm_id}


@router.post("/mark")
async def mark_alarm_processed(request: AlarmMarkRequest, db: Session = Depends(get_db)):
    """批量标记告警为已处理"""
    updated_count = 0
    
    for alarm_id in request.alarm_ids:
        # 更新各模块告警表
        for model in [AlarmBanner, AlarmAbsent, AlarmLoitering, AlarmGathering]:
            alarm = db.query(model).filter(model.id == alarm_id).first()
            if alarm:
                alarm.status = 1
                updated_count += 1
                break
    
    db.commit()
    return {"message": "标记成功", "updated_count": updated_count}


@router.get("/export")
async def export_alarms(
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    event_id: Optional[str] = None,
    format: str = "xlsx"
):
    """导出告警记录"""
    # TODO: 实现导出功能
    return {"message": "导出功能待实现", "format": format}


@router.get("/types")
async def get_alarm_types():
    """获取所有告警类型"""
    return {
        "types": [
            {"event_id": "01", "name": "横幅识别", "alarm_types": ["违规横幅"]},
            {"event_id": "02", "name": "离岗识别", "alarm_types": ["离岗首次告警", "离岗持续告警", "离岗告警解除"]},
            {"event_id": "03", "name": "徘徊警告", "alarm_types": ["徘徊告警", "徘徊告警解除"]},
            {"event_id": "04", "name": "聚集警告", "alarm_types": ["聚集告警", "聚集告警解除"]}
        ]
    }
