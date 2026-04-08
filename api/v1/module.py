from fastapi import APIRouter


router = APIRouter(prefix="/module", tags=["module"])


@router.get("/status")
async def get_module_status():
    """获取各模块状态"""
    return {
        "modules": {
            "gathering": {"status": "running", "enabled": True},
            "loitering": {"status": "running", "enabled": True},
            "banner": {"status": "running", "enabled": True},
            "absent": {"status": "running", "enabled": True}
        }
    }
