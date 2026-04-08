from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import sys

from config.app_config import app_settings
from api.v1 import source, banner, absent, loitering, gathering, alarm, system, module

logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=app_settings.log_level
)

app = FastAPI(
    title=app_settings.app_name,
    version=app_settings.version,
    debug=app_settings.debug
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(source.router, prefix="/api/v1")
app.include_router(banner.router, prefix="/api/v1")
app.include_router(absent.router, prefix="/api/v1")
app.include_router(loitering.router, prefix="/api/v1")
app.include_router(gathering.router, prefix="/api/v1")
app.include_router(alarm.router, prefix="/api/v1")
app.include_router(system.router, prefix="/api/v1")
app.include_router(module.router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"message": "ABRS API", "version": app_settings.version}


@app.get("/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=app_settings.host, port=app_settings.port)
