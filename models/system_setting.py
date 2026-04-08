from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime
from models.base import Base


class SystemSetting(Base):
    __tablename__ = 't_system_setting'

    id = Column(Integer, primary_key=True, autoincrement=True)
    setting_key = Column(String(50), nullable=False)
    setting_value = Column(Text)
    module = Column(String(20), nullable=False)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)
