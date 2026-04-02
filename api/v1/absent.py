from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from models.base import get_db
from models.absent import Person, AlarmAbsent
from core.absent import face_recognizer, stream_manager, absent_detector
import cv2
import numpy as np
import base64


router = APIRouter(prefix="/absent", tags=["absent"])


class PersonInfo(BaseModel):
    person_id: str
    name: str
    post: str
    duty_period: str
    max_absent_min: float = 5.0
    face_img: Optional[str] = None


class PersonUpdateInfo(BaseModel):
    person_id: str
    name: Optional[str] = None
    post: Optional[str] = None
    duty_period: Optional[str] = None
    max_absent_min: Optional[float] = None
    face_feature: Optional[str] = None


class SourceSwitchInfo(BaseModel):
    source_type: str  # camera/file/stream
    source_id: str
    device_id: Optional[int] = 0
    source_addr: Optional[str] = None


class StartDetectionInfo(BaseModel):
    source_id: str


@router.post("/person/add")
async def add_person(person: PersonInfo, db: Session = Depends(get_db)):
    """新增离岗人员，支持面部特征提取"""
    face_feature = None
    
    # 如果提供了面部图片，提取特征
    if person.face_img:
        try:
            # 解码Base64图片
            img_data = base64.b64decode(person.face_img)
            nparr = np.frombuffer(img_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is not None:
                # 提取面部特征
                face_feature = face_recognizer.register_person(person.person_id, img)
                if face_feature is None:
                    return {"error": "无法从图片中提取面部特征，请确保图片包含清晰的人脸"}
        except Exception as e:
            return {"error": f"面部特征提取失败: {str(e)}"}
    
    db_person = Person(
        person_id=person.person_id,
        name=person.name,
        post=person.post,
        duty_period=person.duty_period,
        max_absent_min=person.max_absent_min,
        face_feature=face_feature
    )
    db.add(db_person)
    db.commit()
    db.refresh(db_person)
    
    return {
        "message": "人员添加成功", 
        "person_id": person.person_id,
        "face_feature_extracted": face_feature is not None
    }


@router.post("/person/update")
async def update_person(info: PersonUpdateInfo, db: Session = Depends(get_db)):
    """修改人员信息"""
    db_person = db.query(Person).filter(Person.person_id == info.person_id).first()
    if not db_person:
        return {"error": "人员不存在", "person_id": info.person_id}
    
    if info.name:
        db_person.name = info.name
    if info.post:
        db_person.post = info.post
    if info.duty_period:
        db_person.duty_period = info.duty_period
    if info.max_absent_min is not None:
        db_person.max_absent_min = info.max_absent_min
    if info.face_feature:
        db_person.face_feature = info.face_feature
    
    db.commit()
    return {"message": "人员更新成功", "person_id": info.person_id}


@router.post("/person/delete")
async def delete_person(person_id: str, db: Session = Depends(get_db)):
    """删除人员信息"""
    db_person = db.query(Person).filter(Person.person_id == person_id).first()
    if not db_person:
        return {"error": "人员不存在", "person_id": person_id}
    
    db.delete(db_person)
    db.commit()
    return {"message": "人员删除成功", "person_id": person_id}


@router.get("/person/query")
async def query_persons(person_id: Optional[str] = None, db: Session = Depends(get_db)):
    """查询人员列表"""
    if person_id:
        persons = db.query(Person).filter(Person.person_id == person_id).all()
    else:
        persons = db.query(Person).all()
    
    result = []
    for p in persons:
        result.append({
            "person_id": p.person_id,
            "name": p.name,
            "post": p.post,
            "duty_period": p.duty_period,
            "max_absent_min": p.max_absent_min,
            "has_face_feature": p.face_feature is not None,
            "create_time": p.create_time.isoformat() if p.create_time else None
        })
    return {"persons": result}


@router.post("/source/switch")
async def switch_source(info: SourceSwitchInfo, db: Session = Depends(get_db)):
    """切换输入源"""
    # 如果正在检测，先停止
    if stream_manager.is_detecting:
        stream_manager.stop_detection()
    
    # 启动新的检测
    success = stream_manager.start_detection(
        source_type=info.source_type,
        source_id=info.source_id,
        db_session=db,
        device_id=info.device_id or 0,
        source_addr=info.source_addr
    )
    
    if success:
        return {
            "message": "输入源切换成功",
            "source_type": info.source_type,
            "source_id": info.source_id
        }
    else:
        return {
            "error": "输入源切换失败，请检查视频源是否可用",
            "source_type": info.source_type,
            "source_id": info.source_id
        }


@router.post("/start")
async def start_detection(info: StartDetectionInfo, db: Session = Depends(get_db)):
    """启动离岗识别"""
    if stream_manager.is_detecting:
        return {"error": "检测已在运行中，请先停止"}
    
    # 从数据库获取视频源配置
    from models.video_source import VideoSource
    source = db.query(VideoSource).filter(VideoSource.source_id == info.source_id).first()
    
    if not source:
        return {"error": f"视频源 {info.source_id} 不存在"}
    
    success = stream_manager.start_detection(
        source_type=source.source_type,
        source_id=info.source_id,
        db_session=db,
        device_id=source.device_id,
        source_addr=source.source_addr
    )
    
    if success:
        return {
            "message": "离岗识别已启动",
            "source_id": info.source_id,
            "source_type": source.source_type
        }
    else:
        return {
            "error": "启动失败，请检查视频源配置",
            "source_id": info.source_id
        }


@router.post("/stop")
async def stop_detection():
    """停止离岗识别"""
    if not stream_manager.is_detecting:
        return {"message": "检测未在运行"}
    
    stream_manager.stop_detection()
    return {"message": "离岗识别已停止"}


@router.get("/status")
async def get_status():
    """获取检测状态"""
    return stream_manager.get_status()


@router.get("/alarm/list")
async def get_alarms(
    person_id: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """查询告警记录"""
    query = db.query(AlarmAbsent)
    
    if person_id:
        query = query.filter(AlarmAbsent.content.contains(f'"person_id": "{person_id}"'))
    if start_time:
        query = query.filter(AlarmAbsent.alarm_time >= start_time)
    if end_time:
        query = query.filter(AlarmAbsent.alarm_time <= end_time)
    
    alarms = query.order_by(AlarmAbsent.alarm_time.desc()).all()
    
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
