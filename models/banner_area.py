from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from models.base import Base


class BannerArea(Base):
    __tablename__ = "t_banner_area"

    id = Column(Integer, primary_key=True, autoincrement=True)
    area_id = Column(String(50), unique=True, nullable=False, comment="区域ID")
    area_name = Column(String(100), nullable=False, comment="区域名称")
    coords = Column(String(200), nullable=False, comment="区域坐标")
    is_enable = Column(Integer, default=1, comment="0禁用/1启用")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
