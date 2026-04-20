from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, Float
from datetime import datetime
from models.base import Base


class Person(Base):
    __tablename__ = "t_person"

    id = Column(Integer, primary_key=True, autoincrement=True)
    person_id = Column(String(20), unique=True, nullable=False, comment="人员工号")
    name = Column(String(50), nullable=False, comment="姓名")
    post = Column(String(50), nullable=False, comment="岗位")
    duty_period = Column(String(50), nullable=False, comment="站岗时间段")
    max_absent_min = Column(Float, default=5.0, comment="允许最长离岗时间(分钟，支持小数)")
    face_img = Column(Text, nullable=True, comment="人脸图片Base64")
    face_feature = Column(Text, nullable=True, comment="面部特征值")
    face_detection_box = Column(String(100), nullable=True, comment="人脸检测框坐标JSON[x,y,w,h]")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")


class AlarmAbsent(Base):
    __tablename__ = "t_alarm_absent"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alarm_time = Column(DateTime, nullable=False, comment="告警时间")
    event_id = Column(String(2), default="02", comment="事件编号")
    alarm_type = Column(String(20), nullable=False, comment="告警类型")
    content = Column(JSON, nullable=False, comment="告警内容")
    source_type = Column(String(10), nullable=False, comment="输入源类型")
    source_id = Column(String(20), nullable=False, comment="输入源编号")
    message_id = Column(String(100), unique=True, nullable=False, comment="RabbitMQ消息ID")
    status = Column(Integer, default=0, comment="0未处理/1已查看")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
