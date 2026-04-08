from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Dict, Optional, List
from sqlalchemy.orm import Session
from models.base import get_db
from models.system_setting import SystemSetting
from datetime import datetime
import time
import redis
import pika
from config.db_config import db_settings
from config.rabbitmq_config import rabbitmq_settings


router = APIRouter(prefix="/system", tags=["system"])

# 系统启动时间
_system_start_time = time.time()


class ModelParamsUpdate(BaseModel):
    yolo_confidence: Optional[float] = 0.5
    yolo_iou: Optional[float] = 0.45
    fps: Optional[int] = 10
    resolution: Optional[str] = "1080p"


@router.get("/info")
async def get_system_info():
    """获取系统基本信息"""
    uptime_seconds = int(time.time() - _system_start_time)
    return {
        "app_name": "ABRS",
        "version": "1.0.0",
        "start_time": datetime.fromtimestamp(_system_start_time).strftime("%Y-%m-%d %H:%M:%S"),
        "uptime_seconds": uptime_seconds,
        "modules": ["banner", "absent", "loitering", "gathering"]
    }


@router.get("/redis/status")
async def get_redis_status():
    """获取Redis连接状态"""
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, socket_connect_timeout=2)
        start = time.time()
        r.ping()
        latency_ms = int((time.time() - start) * 1000)
        return {"status": "connected", "latency_ms": latency_ms}
    except Exception as e:
        return {"status": "disconnected", "error": str(e)}


@router.get("/mysql/status")
async def get_mysql_status():
    """获取MySQL连接状态"""
    try:
        import pymysql
        start = time.time()
        conn = pymysql.connect(
            host=db_settings.host,
            port=db_settings.port,
            user=db_settings.user,
            password=db_settings.password,
            database=db_settings.database,
            connect_timeout=2
        )
        conn.ping()
        latency_ms = int((time.time() - start) * 1000)
        conn.close()
        return {"status": "connected", "latency_ms": latency_ms}
    except Exception as e:
        return {"status": "disconnected", "error": str(e)}


@router.get("/rabbitmq/status")
async def get_rabbitmq_status():
    """获取RabbitMQ连接状态"""
    try:
        import pika
        start = time.time()
        credentials = pika.PlainCredentials(
            rabbitmq_settings.username,
            rabbitmq_settings.password
        )
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=rabbitmq_settings.host,
                port=rabbitmq_settings.port,
                credentials=credentials,
                socket_timeout=2
            )
        )
        channel = connection.channel()
        
        # 获取队列信息
        queues = []
        queue_names = ["warning_banner", "warning_absent", "warning_loitering", "warning_gathering"]
        for queue_name in queue_names:
            try:
                queue = channel.queue_declare(queue=queue_name, passive=True)
                queues.append({"name": queue_name, "messages": queue.method.message_count})
            except:
                queues.append({"name": queue_name, "messages": 0})
        
        connection.close()
        latency_ms = int((time.time() - start) * 1000)
        return {"status": "connected", "latency_ms": latency_ms, "queues": queues}
    except Exception as e:
        return {"status": "disconnected", "error": str(e), "queues": []}


@router.get("/logs")
async def get_system_logs(
    level: Optional[str] = None,
    module: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = 100
):
    """查询系统日志"""
    # TODO: 从日志文件或数据库中查询日志
    return {
        "logs": [
            {
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "level": "INFO",
                "module": "system",
                "message": "系统运行正常"
            }
        ],
        "total": 1
    }


@router.get("/model/params")
async def get_model_params(db: Session = Depends(get_db)):
    """获取模型参数"""
    setting = db.query(SystemSetting).filter(
        SystemSetting.setting_key == "model_params",
        SystemSetting.module == "global"
    ).first()
    
    if setting and setting.setting_value:
        import json
        return json.loads(setting.setting_value)
    
    # 返回默认值
    return {
        "yolo_confidence": 0.5,
        "yolo_iou": 0.45,
        "fps": 10,
        "resolution": "1080p"
    }


@router.post("/model/params/update")
async def update_model_params(params: ModelParamsUpdate, db: Session = Depends(get_db)):
    """更新模型参数"""
    import json
    
    setting = db.query(SystemSetting).filter(
        SystemSetting.setting_key == "model_params",
        SystemSetting.module == "global"
    ).first()
    
    params_dict = params.model_dump()
    
    if setting:
        setting.setting_value = json.dumps(params_dict)
    else:
        setting = SystemSetting(
            setting_key="model_params",
            setting_value=json.dumps(params_dict),
            module="global"
        )
        db.add(setting)
    
    db.commit()
    return {"message": "模型参数更新成功", "params": params_dict}
