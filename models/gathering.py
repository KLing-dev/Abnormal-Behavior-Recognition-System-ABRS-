from sqlalchemy import Column, Integer, String, JSON, DateTime
from datetime import datetime
from models.base import Base


class AreaGathering(Base):
    __tablename__ = "t_area_gathering"

    id = Column(Integer, primary_key=True, autoincrement=True)
    area_id = Column(String(10), unique=True, nullable=False, comment="区域编号")
    area_name = Column(String(50), nullable=False, comment="区域名称")
    coords = Column(String(200), nullable=False, comment="区域坐标")
    level_thresholds = Column(JSON, nullable=False, comment="等级阈值（JSON：light/medium/urgent）")
    is_enable = Column(Integer, default=1, comment="1启用/0禁用")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")


class AlarmGathering(Base):
    __tablename__ = "t_alarm_gathering"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alarm_time = Column(DateTime, nullable=False, comment="告警时间")
    event_id = Column(String(2), default="04", comment="事件编号")
    alarm_type = Column(String(20), nullable=False, comment="告警类型")
    content = Column(JSON, nullable=False, comment="告警内容")
    source_type = Column(String(10), nullable=False, comment="输入源类型")
    source_id = Column(String(20), nullable=False, comment="输入源编号")
    message_id = Column(String(100), unique=True, nullable=False, comment="RabbitMQ消息ID")
    status = Column(Integer, default=0, comment="0未处理/1已查看")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
