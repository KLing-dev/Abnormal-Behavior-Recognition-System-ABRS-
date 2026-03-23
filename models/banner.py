from sqlalchemy import Column, Integer, String, JSON, DateTime
from datetime import datetime
from models.base import Base


class AlarmBanner(Base):
    __tablename__ = "t_alarm_banner"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alarm_time = Column(DateTime, nullable=False, comment="告警时间")
    event_id = Column(String(2), default="01", comment="事件编号")
    alarm_type = Column(String(20), nullable=False, comment="告警类型")
    content = Column(JSON, nullable=False, comment="告警内容")
    source_type = Column(String(10), nullable=False, comment="输入源类型")
    source_id = Column(String(20), nullable=False, comment="输入源编号")
    message_id = Column(String(100), unique=True, nullable=False, comment="RabbitMQ消息ID")
    status = Column(Integer, default=0, comment="0未处理/1已查看")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
