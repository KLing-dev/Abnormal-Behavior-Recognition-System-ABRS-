"""
ABRS 聚集检测模块独立启动脚本
端口: 8004
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import sys
import uvicorn

from config.app_config import app_settings
from api.v1 import gathering, alarm

# 配置日志
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=app_settings.log_level
)

# 创建FastAPI应用
app = FastAPI(
    title="ABRS Gathering Detection Module",
    version=app_settings.version,
    description="人员聚集检测模块 - 提供区域聚集检测、告警管理等功能",
    debug=app_settings.debug
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(gathering.router, prefix="/api/v1")
app.include_router(alarm.router, prefix="/api/v1")


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "ABRS Gathering Detection Module",
        "version": app_settings.version,
        "port": 8004
    }


@app.get("/health")
async def health():
    """健康检查"""
    return {
        "status": "healthy",
        "module": "gathering",
        "port": 8004
    }


@app.get("/api/v1/info")
async def module_info():
    """模块信息"""
    return {
        "module_name": "聚集检测模块",
        "module_code": "gathering",
        "event_id": "04",
        "version": app_settings.version,
        "features": [
            "区域聚集检测",
            "多级告警阈值",
            "实时视频处理",
            "告警历史记录"
        ]
    }


if __name__ == "__main__":
    logger.info("Starting ABRS Gathering Detection Module on port 8004")
    uvicorn.run(
        "run_gathering:app",
        host=app_settings.host,
        port=8004,
        reload=app_settings.debug,
        log_level=app_settings.log_level.lower()
    )
