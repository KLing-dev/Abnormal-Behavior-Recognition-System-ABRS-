from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from models.base import get_db
from models.banner import AlarmBanner
from models.gathering import AlarmGathering
from models.loitering import AlarmLoitering
from models.absent import AlarmAbsent


router = APIRouter(prefix="/alarm", tags=["alarm"])


class AlarmUpdateStatus(BaseModel):
    status: int


@router.get("/list")
async def get_alarms(
    event_id: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    status: Optional[int] = None,
    db: Session = Depends(get_db)
):
    alarms = []

    query_params = {}
    if event_id:
        query_params["event_id"] = event_id
    if status is not None:
        query_params["status"] = status

    banner_alarms = db.query(AlarmBanner).filter_by(**query_params).all()
    for alarm in banner_alarms:
        alarms.append({
            "id": alarm.id,
            "alarm_time": alarm.alarm_time.strftime("%Y-%m-%d %H:%M:%S") if alarm.alarm_time else None,
            "event_id": alarm.event_id,
            "alarm_type": alarm.alarm_type,
            "content": alarm.content,
            "source_type": alarm.source_type,
            "source_id": alarm.source_id,
            "message_id": alarm.message_id,
            "status": alarm.status,
            "module": "banner"
        })

    gathering_alarms = db.query(AlarmGathering).filter_by(**query_params).all()
    for alarm in gathering_alarms:
        alarms.append({
            "id": alarm.id,
            "alarm_time": alarm.alarm_time.strftime("%Y-%m-%d %H:%M:%S") if alarm.alarm_time else None,
            "event_id": alarm.event_id,
            "alarm_type": alarm.alarm_type,
            "content": alarm.content,
            "source_type": alarm.source_type,
            "source_id": alarm.source_id,
            "message_id": alarm.message_id,
            "status": alarm.status,
            "module": "gathering"
        })

    loitering_alarms = db.query(AlarmLoitering).filter_by(**query_params).all()
    for alarm in loitering_alarms:
        alarms.append({
            "id": alarm.id,
            "alarm_time": alarm.alarm_time.strftime("%Y-%m-%d %H:%M:%S") if alarm.alarm_time else None,
            "event_id": alarm.event_id,
            "alarm_type": alarm.alarm_type,
            "content": alarm.content,
            "source_type": alarm.source_type,
            "source_id": alarm.source_id,
            "message_id": alarm.message_id,
            "status": alarm.status,
            "module": "loitering"
        })

    absent_alarms = db.query(AlarmAbsent).filter_by(**query_params).all()
    for alarm in absent_alarms:
        alarms.append({
            "id": alarm.id,
            "alarm_time": alarm.alarm_time.strftime("%Y-%m-%d %H:%M:%S") if alarm.alarm_time else None,
            "event_id": alarm.event_id,
            "alarm_type": alarm.alarm_type,
            "content": alarm.content,
            "source_type": alarm.source_type,
            "source_id": alarm.source_id,
            "message_id": alarm.message_id,
            "status": alarm.status,
            "module": "absent"
        })

    if start_time:
        alarms = [a for a in alarms if a["alarm_time"] and a["alarm_time"] >= start_time]
    if end_time:
        alarms = [a for a in alarms if a["alarm_time"] and a["alarm_time"] <= end_time]

    alarms.sort(key=lambda x: x["alarm_time"] or "", reverse=True)

    return {"message": "success", "alarms": alarms}


@router.put("/{alarm_id}/status")
async def update_alarm_status(
    alarm_id: int,
    data: AlarmUpdateStatus,
    db: Session = Depends(get_db)
):
    updated = False

    alarm = db.query(AlarmBanner).filter(AlarmBanner.id == alarm_id).first()
    if alarm:
        alarm.status = data.status
        db.commit()
        updated = True

    if not updated:
        alarm = db.query(AlarmGathering).filter(AlarmGathering.id == alarm_id).first()
        if alarm:
            alarm.status = data.status
            db.commit()
            updated = True

    if not updated:
        alarm = db.query(AlarmLoitering).filter(AlarmLoitering.id == alarm_id).first()
        if alarm:
            alarm.status = data.status
            db.commit()
            updated = True

    if not updated:
        alarm = db.query(AlarmAbsent).filter(AlarmAbsent.id == alarm_id).first()
        if alarm:
            alarm.status = data.status
            db.commit()
            updated = True

    if updated:
        return {"message": "success"}
    return {"message": "alarm not found"}


@router.get("/statistics")
async def get_statistics(
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    db: Session = Depends(get_db)
):
    banner_count = db.query(AlarmBanner).count()
    gathering_count = db.query(AlarmGathering).count()
    loitering_count = db.query(AlarmLoitering).count()
    absent_count = db.query(AlarmAbsent).count()

    banner_unprocessed = db.query(AlarmBanner).filter(AlarmBanner.status == 0).count()
    gathering_unprocessed = db.query(AlarmGathering).filter(AlarmGathering.status == 0).count()
    loitering_unprocessed = db.query(AlarmLoitering).filter(AlarmLoitering.status == 0).count()
    absent_unprocessed = db.query(AlarmAbsent).filter(AlarmAbsent.status == 0).count()

    return {
        "message": "success",
        "data": {
            "total": {
                "banner": banner_count,
                "gathering": gathering_count,
                "loitering": loitering_count,
                "absent": absent_count,
                "all": banner_count + gathering_count + loitering_count + absent_count
            },
            "unprocessed": {
                "banner": banner_unprocessed,
                "gathering": gathering_unprocessed,
                "loitering": loitering_unprocessed,
                "absent": absent_unprocessed,
                "all": banner_unprocessed + gathering_unprocessed + loitering_unprocessed + absent_unprocessed
            }
        }
    }
