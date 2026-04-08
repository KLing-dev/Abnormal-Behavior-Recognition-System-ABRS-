from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional, Dict
from sqlalchemy.orm import Session
from models.base import get_db
from models.gathering import AreaGathering, AlarmGathering


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
    db: Session = Depends(get_db)
):
    query = db.query(AlarmGathering)

    if area_id:
        query = query.filter(AlarmGathering.content.contains(f'"area_id": "{area_id}"'))
    if start_time:
        query = query.filter(AlarmGathering.alarm_time >= start_time)
    if end_time:
        query = query.filter(AlarmGathering.alarm_time <= end_time)

    alarms = query.order_by(AlarmGathering.alarm_time.desc()).all()

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


# 新增接口：获取检测状态
@router.get("/status")
async def get_status():
    """获取聚集检测实时状态"""
    return {
        "is_running": False,
        "source_id": None,
        "source_type": None,
        "areas_count": 0,
        "current_alarms": []
    }


# 新增接口：设置查询和更新
@router.get("/setting/query")
async def get_settings(db: Session = Depends(get_db)):
    """查询聚集检测全局设置"""
    from models.system_setting import SystemSetting
    import json

    settings = db.query(SystemSetting).filter(SystemSetting.module == "gathering").all()
    result = {
        "trigger_duration_sec": 180,
        "clear_duration_sec": 300,
        "level_thresholds": {"light": 5, "medium": 10, "urgent": 20}
    }

    for s in settings:
        if s.setting_key == "trigger_duration_sec":
            result["trigger_duration_sec"] = int(s.setting_value)
        elif s.setting_key == "clear_duration_sec":
            result["clear_duration_sec"] = int(s.setting_value)
        elif s.setting_key == "level_thresholds":
            result["level_thresholds"] = json.loads(s.setting_value)

    return result


class GatheringSettingsUpdate(BaseModel):
    trigger_duration_sec: Optional[int] = 180
    clear_duration_sec: Optional[int] = 300
    level_thresholds: Optional[Dict] = None


@router.post("/setting/update")
async def update_settings(settings: GatheringSettingsUpdate, db: Session = Depends(get_db)):
    """更新聚集检测全局设置"""
    from models.system_setting import SystemSetting
    import json

    # 更新触发时长
    trigger_setting = db.query(SystemSetting).filter(
        SystemSetting.setting_key == "trigger_duration_sec",
        SystemSetting.module == "gathering"
    ).first()

    if trigger_setting:
        trigger_setting.setting_value = str(settings.trigger_duration_sec)
    else:
        trigger_setting = SystemSetting(
            setting_key="trigger_duration_sec",
            setting_value=str(settings.trigger_duration_sec),
            module="gathering"
        )
        db.add(trigger_setting)

    # 更新清除时长
    clear_setting = db.query(SystemSetting).filter(
        SystemSetting.setting_key == "clear_duration_sec",
        SystemSetting.module == "gathering"
    ).first()

    if clear_setting:
        clear_setting.setting_value = str(settings.clear_duration_sec)
    else:
        clear_setting = SystemSetting(
            setting_key="clear_duration_sec",
            setting_value=str(settings.clear_duration_sec),
            module="gathering"
        )
        db.add(clear_setting)

    # 更新等级阈值
    if settings.level_thresholds:
        level_setting = db.query(SystemSetting).filter(
            SystemSetting.setting_key == "level_thresholds",
            SystemSetting.module == "gathering"
        ).first()

        if level_setting:
            level_setting.setting_value = json.dumps(settings.level_thresholds)
        else:
            level_setting = SystemSetting(
                setting_key="level_thresholds",
                setting_value=json.dumps(settings.level_thresholds),
                module="gathering"
            )
            db.add(level_setting)

    db.commit()
    return {"message": "设置更新成功"}
