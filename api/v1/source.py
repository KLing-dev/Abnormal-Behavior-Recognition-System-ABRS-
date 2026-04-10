from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from models.video_source import VideoSource as VideoSourceModel
from models.base import get_db


router = APIRouter(prefix="/source", tags=["source"])


class VideoSource(BaseModel):
    source_id: str
    source_name: str
    source_type: str
    device_id: Optional[int] = None
    source_addr: Optional[str] = None
    is_enable: bool = True

    class Config:
        from_attributes = True


class SourceDeleteRequest(BaseModel):
    source_id: str


@router.post("/add")
async def add_source(source: VideoSource, db: Session = Depends(get_db)):
    """添加视频源"""
    # 检查是否已存在
    existing = db.query(VideoSourceModel).filter(VideoSourceModel.source_id == source.source_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="源ID已存在")
    
    # 创建新记录
    db_source = VideoSourceModel(
        source_id=source.source_id,
        source_name=source.source_name,
        source_type=source.source_type,
        device_id=source.device_id,
        source_addr=source.source_addr,
        is_enable=1 if source.is_enable else 0
    )
    db.add(db_source)
    db.commit()
    db.refresh(db_source)
    
    return {
        "message": "添加成功",
        "source": {
            "source_id": db_source.source_id,
            "source_name": db_source.source_name,
            "source_type": db_source.source_type,
            "device_id": db_source.device_id,
            "source_addr": db_source.source_addr,
            "is_enable": db_source.is_enable
        }
    }


@router.post("/update")
async def update_source(source: VideoSource, db: Session = Depends(get_db)):
    """更新视频源"""
    db_source = db.query(VideoSourceModel).filter(VideoSourceModel.source_id == source.source_id).first()
    if not db_source:
        raise HTTPException(status_code=404, detail="视频源不存在")
    
    db_source.source_name = source.source_name
    db_source.source_type = source.source_type
    db_source.device_id = source.device_id
    db_source.source_addr = source.source_addr
    db_source.is_enable = 1 if source.is_enable else 0
    
    db.commit()
    db.refresh(db_source)
    
    return {
        "message": "更新成功",
        "source": {
            "source_id": db_source.source_id,
            "source_name": db_source.source_name,
            "source_type": db_source.source_type,
            "device_id": db_source.device_id,
            "source_addr": db_source.source_addr,
            "is_enable": db_source.is_enable
        }
    }


@router.post("/delete")
async def delete_source(request: SourceDeleteRequest, db: Session = Depends(get_db)):
    """删除视频源"""
    db_source = db.query(VideoSourceModel).filter(VideoSourceModel.source_id == request.source_id).first()
    if not db_source:
        raise HTTPException(status_code=404, detail="视频源不存在")
    
    db.delete(db_source)
    db.commit()
    
    return {"message": "删除成功", "source_id": request.source_id}


@router.get("/list")
async def list_sources(db: Session = Depends(get_db)):
    """获取视频源列表"""
    sources = db.query(VideoSourceModel).all()
    return {
        "message": "获取成功",
        "sources": [
            {
                "source_id": s.source_id,
                "source_name": s.source_name,
                "source_type": s.source_type,
                "device_id": s.device_id,
                "source_addr": s.source_addr,
                "is_enable": s.is_enable == 1
            }
            for s in sources
        ]
    }


@router.post("/switch")
async def switch_source(source_type: str, source_id: str, device_id: Optional[int] = None, source_addr: Optional[str] = None):
    """切换视频源"""
    return {"message": "切换成功", "source_type": source_type, "source_id": source_id}
