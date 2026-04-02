from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime
from models.base import Base


class VideoSource(Base):
    __tablename__ = "t_video_source"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(String(20), unique=True, nullable=False, comment="输入源编号")
    source_name = Column(String(50), nullable=False, comment="输入源名称")
    source_type = Column(String(10), nullable=False, comment="camera/file/stream")
    device_id = Column(Integer, nullable=True, comment="摄像头设备ID")
    source_addr = Column(Text, nullable=True, comment="本地路径/网络流地址")
    is_enable = Column(Integer, default=1, comment="1启用/0禁用")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
