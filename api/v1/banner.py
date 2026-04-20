import os
import aiofiles
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from loguru import logger
from models.base import get_db
from models.banner import AlarmBanner
from models.banner_area import BannerArea
from models.banner_words import BannerWord
from core.banner.detector import banner_detector
from core.banner.video_processor import banner_processor


router = APIRouter(prefix="/banner", tags=["banner"])


class IllegalWordsUpdate(BaseModel):
    words: list[str]


class AreaInfo(BaseModel):
    area_id: str
    area_name: str
    coords: str
    is_enable: Optional[int] = 1


class AreaUpdateInfo(BaseModel):
    area_id: str
    area_name: Optional[str] = None
    coords: Optional[str] = None
    is_enable: Optional[int] = None


class AreaDeleteRequest(BaseModel):
    area_id: str


@router.post("/illegal-words/update")
async def update_illegal_words(update: IllegalWordsUpdate, db: Session = Depends(get_db)):
    # 清空现有违规词
    db.query(BannerWord).delete()
    db.commit()
    
    # 添加新违规词
    for word in update.words:
        if word.strip():
            db_word = BannerWord(word=word.strip().lower())
            db.add(db_word)
    db.commit()
    
    # 同步到检测器
    banner_detector.load_illegal_words(update.words)
    return {"message": "违规词更新成功", "count": len(update.words)}


@router.get("/illegal-words/query")
async def query_illegal_words(db: Session = Depends(get_db)):
    # 从数据库获取违规词
    words = [w.word for w in db.query(BannerWord).all()]
    # 同步到检测器
    banner_detector.load_illegal_words(words)
    return {"illegal_words": words}


@router.post("/area/add")
async def add_area(area: AreaInfo, db: Session = Depends(get_db)):
    # 检查是否已存在
    existing = db.query(BannerArea).filter(BannerArea.area_id == area.area_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="区域ID已存在")
    
    # 创建新区域
    db_area = BannerArea(
        area_id=area.area_id,
        area_name=area.area_name,
        coords=area.coords,
        is_enable=area.is_enable if area.is_enable is not None else 1
    )
    db.add(db_area)
    db.commit()
    db.refresh(db_area)
    
    # 同步到检测器
    areas_data = [
        {
            "area_id": a.area_id,
            "area_name": a.area_name,
            "coords": a.coords,
            "is_enable": a.is_enable
        }
        for a in db.query(BannerArea).all()
    ]
    banner_detector.load_area_config(areas_data)
    
    return {"message": "区域添加成功", "area_id": area.area_id}


@router.post("/area/update")
async def update_area(info: AreaUpdateInfo, db: Session = Depends(get_db)):
    db_area = db.query(BannerArea).filter(BannerArea.area_id == info.area_id).first()
    if not db_area:
        raise HTTPException(status_code=404, detail="区域不存在")
    
    if info.area_name:
        db_area.area_name = info.area_name
    if info.coords:
        db_area.coords = info.coords
    if info.is_enable is not None:
        db_area.is_enable = info.is_enable
    
    db.commit()
    db.refresh(db_area)
    
    # 同步到检测器
    areas_data = [
        {
            "area_id": a.area_id,
            "area_name": a.area_name,
            "coords": a.coords,
            "is_enable": a.is_enable
        }
        for a in db.query(BannerArea).all()
    ]
    banner_detector.load_area_config(areas_data)
    
    return {"message": "区域更新成功", "area_id": info.area_id}


@router.post("/area/delete")
async def delete_area(request: AreaDeleteRequest, db: Session = Depends(get_db)):
    db_area = db.query(BannerArea).filter(BannerArea.area_id == request.area_id).first()
    if not db_area:
        raise HTTPException(status_code=404, detail="区域不存在")
    
    db.delete(db_area)
    db.commit()
    
    # 同步到检测器
    areas_data = [
        {
            "area_id": a.area_id,
            "area_name": a.area_name,
            "coords": a.coords,
            "is_enable": a.is_enable
        }
        for a in db.query(BannerArea).all()
    ]
    banner_detector.load_area_config(areas_data)
    
    return {"message": "区域删除成功", "area_id": request.area_id}


@router.get("/area/query")
async def query_areas(area_id: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(BannerArea)
    if area_id:
        query = query.filter(BannerArea.area_id == area_id)
    
    areas = query.all()
    return {
        "message": "获取成功",
        "areas": [
            {
                "area_id": a.area_id,
                "area_name": a.area_name,
                "coords": a.coords,
                "is_enable": a.is_enable == 1,
                "create_time": a.create_time.isoformat() if a.create_time else None
            }
            for a in areas
        ]
    }


@router.post("/source/switch")
async def switch_source(source_type: str, source_id: str, source_addr: str = "", device_id: int = 0):
    return {"message": "切换成功", "source_type": source_type, "source_id": source_id}


class StartDetectionRequest(BaseModel):
    source_type: str
    source_id: str
    source_addr: str = ""
    device_id: int = 0
    fps: int = 10


@router.post("/start")
async def start_detection(request: StartDetectionRequest, db: Session = Depends(get_db)):
    # 加载违规词到检测器
    words = [w.word for w in db.query(BannerWord).all()]
    banner_detector.load_illegal_words(words)
    
    # 加载区域配置到检测器
    areas_data = [
        {
            "area_id": a.area_id,
            "area_name": a.area_name,
            "coords": a.coords,
            "is_enable": a.is_enable
        }
        for a in db.query(BannerArea).all()
    ]
    banner_detector.load_area_config(areas_data)
    
    result = banner_processor.start_detection(
        source_type=request.source_type,
        source_id=request.source_id,
        source_addr=request.source_addr,
        device_id=request.device_id,
        fps=request.fps
    )
    if result:
        return {"message": "检测启动成功"}
    else:
        raise HTTPException(status_code=500, detail="检测启动失败，请检查模型文件是否存在")


@router.post("/stop")
async def stop_detection():
    banner_processor.stop_detection()
    return {"message": "检测停止成功"}


@router.get("/status")
async def get_status(db: Session = Depends(get_db)):
    # 从数据库获取区域数量和违规词数量
    areas_count = db.query(BannerArea).count()
    words_count = db.query(BannerWord).count()
    # 从数据库统计告警数量
    alert_count = db.query(AlarmBanner).count()
    return {
        "is_running": banner_processor.is_running,
        "alert_count": alert_count,
        "areas_count": areas_count,
        "illegal_words_count": words_count
    }


class AlarmStatusUpdate(BaseModel):
    status: int


@router.get("/alarm/list")
async def list_alarms(
    area_id: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    status: Optional[int] = None,
    limit: Optional[int] = None,
    db: Session = Depends(get_db)
):
    query = db.query(AlarmBanner)

    if area_id:
        query = query.filter(AlarmBanner.source_id == area_id)
    if start_time:
        query = query.filter(AlarmBanner.alarm_time >= start_time)
    if end_time:
        query = query.filter(AlarmBanner.alarm_time <= end_time)
    if status is not None:
        query = query.filter(AlarmBanner.status == status)

    query = query.order_by(AlarmBanner.alarm_time.desc())

    if limit:
        query = query.limit(limit)

    alarms = query.all()

    return {
        "alarms": [
            {
                "id": a.id,
                "alarm_time": a.alarm_time.isoformat() if a.alarm_time else None,
                "event_id": a.event_id,
                "alarm_type": a.alarm_type,
                "content": a.content,
                "source_type": a.source_type,
                "source_id": a.source_id,
                "status": a.status
            }
            for a in alarms
        ]
    }


@router.put("/alarm/{alarm_id}/status")
async def update_alarm_status(alarm_id: int, data: AlarmStatusUpdate, db: Session = Depends(get_db)):
    alarm = db.query(AlarmBanner).filter(AlarmBanner.id == alarm_id).first()
    if not alarm:
        raise HTTPException(status_code=404, detail="告警不存在")

    alarm.status = data.status
    db.commit()

    return {"message": "success"}


@router.delete("/alarm/{alarm_id}")
async def delete_alarm(alarm_id: int, db: Session = Depends(get_db)):
    alarm = db.query(AlarmBanner).filter(AlarmBanner.id == alarm_id).first()
    if not alarm:
        raise HTTPException(status_code=404, detail="告警不存在")

    # 只允许删除已处理的告警
    if alarm.status != 1:
        raise HTTPException(status_code=400, detail="只能删除已处理的告警")

    db.delete(alarm)
    db.commit()

    return {"message": "success"}


def get_latest_output_video():
    """获取最新的输出视频文件路径"""
    # 确保 output 目录存在
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    # 优先使用当前正在处理的视频
    if banner_processor.output_video_path and os.path.exists(banner_processor.output_video_path):
        return banner_processor.output_video_path
    # 否则从历史列表中找最新的
    for video_path in reversed(banner_processor.output_videos):
        if os.path.exists(video_path):
            return video_path
    # 如果都没有，从文件系统扫描 output 目录
    if os.path.exists(output_dir):
        video_files = [f for f in os.listdir(output_dir) if f.endswith(('.mp4', '.avi'))]
        if video_files:
            # 按修改时间排序，获取最新的
            video_files.sort(key=lambda x: os.path.getmtime(os.path.join(output_dir, x)), reverse=True)
            latest_video = os.path.join(output_dir, video_files[0])
            return os.path.abspath(latest_video)
    return None


@router.get("/output-video")
async def get_output_video():
    """获取处理后的输出视频信息"""
    video_path = get_latest_output_video()
    if video_path:
        filename = os.path.basename(video_path)
        return {
            "has_video": True,
            "filename": filename,
            "url": f"/api/v1/banner/output-video/download"
        }
    return {"has_video": False}


async def iterfile(file_path: str, start: int = 0, end: int = None):
    """异步文件流生成器，支持范围请求"""
    async with aiofiles.open(file_path, "rb") as f:
        await f.seek(start)
        remaining = end - start + 1 if end else None
        while True:
            chunk_size = 8192
            if remaining is not None:
                chunk_size = min(chunk_size, remaining)
            chunk = await f.read(chunk_size)
            if not chunk:
                break
            yield chunk
            if remaining is not None:
                remaining -= len(chunk)
                if remaining <= 0:
                    break


@router.options("/output-video/play")
async def play_output_video_options():
    """处理 CORS 预检请求"""
    return StreamingResponse(
        iter([]),
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "Range, Accept, Content-Type",
            "Access-Control-Max-Age": "86400"
        }
    )


@router.get("/output-video/play")
async def play_output_video(request: Request):
    """播放输出视频（用于网页播放器），支持范围请求"""
    video_path = get_latest_output_video()
    if not video_path:
        raise HTTPException(status_code=404, detail="视频文件不存在")

    file_size = os.path.getsize(video_path)
    range_header = request.headers.get("range")

    # 基础响应头，支持 CORS 和视频播放
    base_headers = {
        "Accept-Ranges": "bytes",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
        "Access-Control-Allow-Headers": "Range, Accept, Content-Type",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    }

    if range_header:
        # 解析范围请求头，例如 "bytes=0-1023" 或 "bytes=0-"
        try:
            range_value = range_header.replace("bytes=", "").strip()
            if "-" in range_value:
                start_str, end_str = range_value.split("-", 1)
                start = int(start_str) if start_str else 0
                end = int(end_str) if end_str else file_size - 1

                if start >= file_size:
                    raise HTTPException(status_code=416, detail="Range not satisfiable")

                end = min(end, file_size - 1)
                content_length = end - start + 1

                headers = {
                    **base_headers,
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Content-Length": str(content_length)
                }

                return StreamingResponse(
                    iterfile(video_path, start, end),
                    media_type="video/mp4",
                    status_code=206,
                    headers=headers
                )
        except (ValueError, IndexError) as e:
            logger.warning(f"Failed to parse range header '{range_header}': {e}")

    # 非范围请求，返回整个文件
    headers = {
        **base_headers,
        "Content-Length": str(file_size)
    }

    return StreamingResponse(
        iterfile(video_path),
        media_type="video/mp4",
        headers=headers
    )


@router.get("/output-video/download")
async def download_output_video():
    """下载输出视频"""
    video_path = get_latest_output_video()
    if not video_path:
        raise HTTPException(status_code=404, detail="视频文件不存在")

    file_size = os.path.getsize(video_path)
    filename = os.path.basename(video_path)

    return StreamingResponse(
        iterfile(video_path),
        media_type="video/mp4",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(file_size)
        }
    )


@router.get("/stream")
async def video_stream():
    """MJPEG视频流端点"""

    async def generate():
        if not banner_processor.is_running:
            # 检测未运行时返回一个黑色帧
            import cv2
            import numpy as np
            black_frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(black_frame, "Detection Stopped", (150, 240),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            _, buffer = cv2.imencode('.jpg', black_frame)
            frame_bytes = buffer.tobytes()
            yield (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n'
                b'Content-Length: ' + str(len(frame_bytes)).encode() + b'\r\n'
                b'\r\n' + frame_bytes + b'\r\n'
            )
            return

        for frame in banner_processor.generate_mjpeg_stream():
            yield frame

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "*"
        }
    )
