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
    face_img: Optional[str] = None


class FaceDetectionResult(BaseModel):
    success: bool
    message: str
    detection_box: Optional[list] = None
    face_img: Optional[str] = None


class SourceSwitchInfo(BaseModel):
    source_type: str  # camera/file/stream
    source_id: str
    device_id: Optional[int] = 0
    source_addr: Optional[str] = None


class StartDetectionInfo(BaseModel):
    source_id: str


def decode_base64_image(base64_str: str) -> bytes:
    """解码Base64图片，支持data URI格式"""
    # 去除data URI前缀 (如: data:image/jpeg;base64,)
    if ',' in base64_str:
        base64_str = base64_str.split(',')[1]
    # 去除空白字符
    base64_str = base64_str.strip()
    return base64.b64decode(base64_str)


@router.post("/person/add")
async def add_person(person: PersonInfo, db: Session = Depends(get_db)):
    """新增离岗人员，支持面部特征提取"""
    face_feature = None
    face_img_data = None
    detection_box = None

    # 如果提供了面部图片，先检测人脸，再提取特征
    if person.face_img:
        try:
            # 解码Base64图片（支持data URI格式）
            img_data = decode_base64_image(person.face_img)
            nparr = np.frombuffer(img_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if img is None:
                return {"error": "图片解码失败，请确保上传有效的图片文件"}

            # 检测人脸
            faces = face_recognizer.detect_faces(img)

            if not faces:
                return {"error": "未检测到人脸，请确保图片中包含清晰的人脸"}

            if len(faces) > 1:
                return {"error": "检测到多张人脸，请上传只包含一张人脸的图片"}

            # 获取人脸区域
            x, y, w, h = faces[0]
            detection_box = [int(x), int(y), int(w), int(h)]

            # 扩展人脸区域（添加一些边距）
            margin = int(min(w, h) * 0.2)
            x1 = max(0, x - margin)
            y1 = max(0, y - margin)
            x2 = min(img.shape[1], x + w + margin)
            y2 = min(img.shape[0], y + h + margin)

            # 裁剪人脸区域
            face_roi = img[y1:y2, x1:x2]

            # 保存处理后的人脸图片
            _, buffer = cv2.imencode('.jpg', face_roi)
            face_img_data = base64.b64encode(buffer).decode('utf-8')

            # 提取面部特征
            face_feature = face_recognizer.register_person(person.person_id, face_roi)
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
        face_img=face_img_data,
        face_feature=face_feature,
        face_detection_box=str(detection_box) if detection_box else None
    )
    db.add(db_person)
    db.commit()
    db.refresh(db_person)

    return {
        "message": "人员添加成功",
        "person_id": person.person_id,
        "face_feature_extracted": face_feature is not None,
        "has_face_img": face_img_data is not None
    }


@router.post("/person/update")
async def update_person(info: PersonUpdateInfo, db: Session = Depends(get_db)):
    """修改人员信息，支持更新人脸图片"""
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

    # 如果提供了新的人脸图片，重新检测并提取特征
    if info.face_img:
        try:
            # 解码Base64图片（支持data URI格式）
            img_data = decode_base64_image(info.face_img)
            nparr = np.frombuffer(img_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if img is None:
                return {"error": "图片解码失败"}

            # 检测人脸
            faces = face_recognizer.detect_faces(img)

            if not faces:
                return {"error": "未检测到人脸，请确保图片中包含清晰的人脸"}

            if len(faces) > 1:
                return {"error": "检测到多张人脸，请上传只包含一张人脸的图片"}

            # 获取人脸区域
            x, y, w, h = faces[0]
            detection_box = [int(x), int(y), int(w), int(h)]

            # 扩展人脸区域
            margin = int(min(w, h) * 0.2)
            x1 = max(0, x - margin)
            y1 = max(0, y - margin)
            x2 = min(img.shape[1], x + w + margin)
            y2 = min(img.shape[0], y + h + margin)

            # 裁剪人脸区域
            face_roi = img[y1:y2, x1:x2]

            # 保存处理后的人脸图片
            _, buffer = cv2.imencode('.jpg', face_roi)
            face_img_data = base64.b64encode(buffer).decode('utf-8')

            # 提取面部特征
            face_feature = face_recognizer.register_person(info.person_id, face_roi)
            if face_feature is None:
                return {"error": "无法从图片中提取面部特征"}

            # 更新数据库
            db_person.face_img = face_img_data
            db_person.face_feature = face_feature
            db_person.face_detection_box = str(detection_box)

        except Exception as e:
            return {"error": f"人脸处理失败: {str(e)}"}

    db.commit()
    return {
        "message": "人员更新成功",
        "person_id": info.person_id,
        "has_face_img": db_person.face_img is not None
    }


@router.post("/person/delete")
async def delete_person(person_id: str, db: Session = Depends(get_db)):
    """删除人员信息"""
    db_person = db.query(Person).filter(Person.person_id == person_id).first()
    if not db_person:
        return {"error": "人员不存在", "person_id": person_id}

    db.delete(db_person)
    db.commit()
    return {"message": "人员删除成功", "person_id": person_id}


@router.post("/face/detect")
async def detect_face(data: dict, db: Session = Depends(get_db)):
    """
    人脸检测与分割API
    接收Base64图片，返回人脸检测框和分割后的人脸图片
    支持调试模式，返回检测详情
    """
    face_img_base64 = data.get("face_img")
    debug_mode = data.get("debug", False)

    if not face_img_base64:
        return {"success": False, "message": "未提供图片"}

    try:
        # 解码Base64图片（支持data URI格式）
        img_data = decode_base64_image(face_img_base64)
        nparr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            return {"success": False, "message": "图片解码失败"}

        # 检测人脸（使用改进的检测逻辑）
        faces = face_recognizer.detect_faces(img)

        # 调试信息
        debug_info = {
            "image_size": [img.shape[1], img.shape[0]],
            "faces_detected": len(faces),
            "faces_details": []
        }

        # 创建可视化结果
        vis_img = img.copy()
        for i, (x, y, w, h) in enumerate(faces):
            # 绘制检测框
            color = (0, 255, 0) if i == 0 else (0, 0, 255)  # 第一张绿色，其他红色
            cv2.rectangle(vis_img, (x, y), (x+w, y+h), color, 2)
            cv2.putText(vis_img, f"Face {i+1}", (x, y-10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

            debug_info["faces_details"].append({
                "index": i,
                "box": [int(x), int(y), int(w), int(h)],
                "area": int(w * h),
                "is_primary": i == 0
            })

        # 编码可视化图片
        _, vis_buffer = cv2.imencode('.jpg', vis_img)
        vis_base64 = base64.b64encode(vis_buffer).decode('utf-8')

        if not faces:
            return {
                "success": False,
                "message": "未检测到人脸，请确保图片中包含清晰的人脸",
                "debug": debug_info if debug_mode else None,
                "visualization": f"data:image/jpeg;base64,{vis_base64}"
            }

        # 如果检测到多张人脸，选择面积最大的一张作为主脸
        if len(faces) > 1:
            # 按面积排序，选择最大的
            faces_with_area = [(i, x, y, w, h, w*h) for i, (x, y, w, h) in enumerate(faces)]
            faces_with_area.sort(key=lambda x: x[5], reverse=True)

            # 如果第二大脸面积小于最大脸的30%，认为是误检
            if len(faces_with_area) >= 2:
                primary_area = faces_with_area[0][5]
                secondary_area = faces_with_area[1][5]
                if secondary_area < primary_area * 0.3:
                    # 使用最大的人脸
                    _, x, y, w, h, _ = faces_with_area[0]
                    faces = [(x, y, w, h)]
                else:
                    return {
                        "success": False,
                        "message": f"检测到{len(faces)}张人脸，请上传只包含一张人脸的图片",
                        "debug": debug_info if debug_mode else None,
                        "visualization": f"data:image/jpeg;base64,{vis_base64}"
                    }

        # 获取人脸区域
        x, y, w, h = faces[0]

        # 扩展人脸区域（添加一些边距）
        margin = int(min(w, h) * 0.2)
        x1 = max(0, x - margin)
        y1 = max(0, y - margin)
        x2 = min(img.shape[1], x + w + margin)
        y2 = min(img.shape[0], y + h + margin)

        # 裁剪人脸区域
        face_roi = img[y1:y2, x1:x2]

        # 编码为Base64
        _, buffer = cv2.imencode('.jpg', face_roi)
        face_roi_base64 = base64.b64encode(buffer).decode('utf-8')

        return {
            "success": True,
            "message": "人脸检测成功",
            "detection_box": [int(x), int(y), int(w), int(h)],
            "face_img": f"data:image/jpeg;base64,{face_roi_base64}",
            "visualization": f"data:image/jpeg;base64,{vis_base64}",
            "debug": debug_info if debug_mode else None
        }

    except Exception as e:
        import traceback
        return {
            "success": False,
            "message": f"人脸检测失败: {str(e)}",
            "error_detail": traceback.format_exc() if debug_mode else None
        }


@router.get("/person/query")
async def query_persons(person_id: Optional[str] = None, db: Session = Depends(get_db)):
    """查询人员列表，包含人脸图片信息"""
    if person_id:
        persons = db.query(Person).filter(Person.person_id == person_id).all()
    else:
        persons = db.query(Person).all()

    result = []
    for p in persons:
        # 构建人脸图片URL（如果存在）
        face_img_url = None
        if p.face_img:
            face_img_url = f"/api/v1/absent/person/{p.person_id}/face"

        result.append({
            "person_id": p.person_id,
            "name": p.name,
            "post": p.post,
            "duty_period": p.duty_period,
            "max_absent_min": p.max_absent_min,
            "has_face_feature": p.face_feature is not None,
            "has_face_img": p.face_img is not None,
            "face_img_url": face_img_url,
            "face_detection_box": p.face_detection_box,
            "create_time": p.create_time.isoformat() if p.create_time else None
        })
    return {"persons": result}


@router.get("/person/{person_id}/face")
async def get_person_face(person_id: str, db: Session = Depends(get_db)):
    """获取人员人脸图片"""
    db_person = db.query(Person).filter(Person.person_id == person_id).first()
    if not db_person or not db_person.face_img:
        raise HTTPException(status_code=404, detail="人脸图片不存在")

    from fastapi.responses import Response
    import base64

    try:
        # 解码Base64图片
        img_data = base64.b64decode(db_person.face_img)
        return Response(content=img_data, media_type="image/jpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图片解码失败: {str(e)}")


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
    status: Optional[int] = None,
    limit: Optional[int] = None,
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
    if status is not None:
        query = query.filter(AlarmAbsent.status == status)
    
    query = query.order_by(AlarmAbsent.alarm_time.desc())
    
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
    unprocessed_count = db.query(AlarmAbsent).filter(AlarmAbsent.status == 0).count()
    processed_count = db.query(AlarmAbsent).filter(AlarmAbsent.status == 1).count()
    
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
    alarm = db.query(AlarmAbsent).filter(AlarmAbsent.id == alarm_id).first()
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
        alarm = db.query(AlarmAbsent).filter(AlarmAbsent.id == alarm_id).first()
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
        alarm = db.query(AlarmAbsent).filter(AlarmAbsent.id == alarm_id).first()
        if alarm:
            db.delete(alarm)
            deleted_count += 1
    
    db.commit()
    
    return {"message": f"成功删除 {deleted_count} 条告警", "deleted_count": deleted_count}


@router.delete("/alarm/{alarm_id}")
async def delete_alarm(alarm_id: int, db: Session = Depends(get_db)):
    """删除单条告警"""
    alarm = db.query(AlarmAbsent).filter(AlarmAbsent.id == alarm_id).first()
    if not alarm:
        raise HTTPException(status_code=404, detail="告警不存在")
    
    db.delete(alarm)
    db.commit()
    
    return {"message": "告警删除成功", "alarm_id": alarm_id}
