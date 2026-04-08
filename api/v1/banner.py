from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from models.base import get_db
from models.banner import AlarmBanner
from core.banner.detector import banner_detector
from core.banner.video_processor import banner_processor


router = APIRouter(prefix="/banner", tags=["banner"])


class IllegalWordsUpdate(BaseModel):
    words: list[str]


class AreaInfo(BaseModel):
    area_id: str
    area_name: str
    coords: str


class AreaUpdateInfo(BaseModel):
    area_id: str
    area_name: Optional[str] = None
    coords: Optional[str] = None
    is_enable: Optional[int] = None


@router.post("/illegal-words/update")
async def update_illegal_words(update: IllegalWordsUpdate):
    banner_detector.load_illegal_words(update.words)
    return {"message": "违规词更新成功", "count": len(update.words)}


@router.get("/illegal-words/query")
async def query_illegal_words():
    return {"illegal_words": banner_detector.illegal_words}


@router.post("/area/add")
async def add_area(area: AreaInfo):
    areas_data = banner_detector.areas.copy()
    areas_data.append({
        "area_id": area.area_id,
        "area_name": area.area_name,
        "coords": area.coords
    })
    banner_detector.load_area_config(areas_data)
    return {"message": "区域添加成功", "area_id": area.area_id}


@router.post("/area/update")
async def update_area(info: AreaUpdateInfo):
    if info.area_id not in banner_detector.areas:
        return {"error": "区域不存在", "area_id": info.area_id}

    area = banner_detector.areas[info.area_id]
    if info.area_name:
        area["area_name"] = info.area_name
    if info.coords:
        area["coords"] = info.coords
    if info.is_enable is not None:
        area["is_enable"] = info.is_enable

    areas_data = list(banner_detector.areas.values())
    banner_detector.load_area_config(areas_data)
    return {"message": "区域更新成功", "area_id": info.area_id}


@router.post("/area/delete")
async def delete_area(area_id: str):
    if area_id in banner_detector.areas:
        del banner_detector.areas[area_id]
    return {"message": "区域删除成功", "area_id": area_id}


@router.get("/area/query")
async def query_areas(area_id: Optional[str] = None):
    if area_id:
        area = banner_detector.areas.get(area_id)
        if not area:
            return {"areas": []}
        return {"areas": [area]}
    return {"areas": list(banner_detector.areas.values())}


@router.post("/source/switch")
async def switch_source(source_type: str, source_id: str, source_addr: str = "", device_id: Optional[int] = None):
    return {"message": "source switched", "source_type": source_type, "source_id": source_id}


@router.post("/start")
async def start_detection(
    source_type: str,
    source_id: str,
    source_addr: str = "",
    device_id: int = 0,
    fps: int = 10
):
    success = banner_processor.start_detection(
        source_type=source_type,
        source_id=source_id,
        source_addr=source_addr,
        device_id=device_id,
        fps=fps
    )
    if success:
        return {"message": "横幅检测已启动", "source_id": source_id}
    return {"error": "横幅检测启动失败"}


@router.post("/stop")
async def stop_detection():
    banner_processor.stop_detection()
    return {"message": "横幅检测已停止"}


@router.get("/status")
async def get_status():
    return {
        "is_running": banner_processor.is_running,
        "alert_count": banner_detector.get_alert_count(),
        "areas_count": len(banner_detector.areas),
        "illegal_words_count": len(banner_detector.illegal_words)
    }


@router.get("/alarm/list")
async def get_alarms(
    area_id: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(AlarmBanner)

    if area_id:
        query = query.filter(AlarmBanner.content.contains(f'"area_id": "{area_id}"'))
    if start_time:
        query = query.filter(AlarmBanner.alarm_time >= start_time)
    if end_time:
        query = query.filter(AlarmBanner.alarm_time <= end_time)

    alarms = query.order_by(AlarmBanner.alarm_time.desc()).all()

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