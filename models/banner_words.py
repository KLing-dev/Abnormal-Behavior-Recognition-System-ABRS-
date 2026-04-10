from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from models.base import Base


class BannerWord(Base):
    __tablename__ = "t_banner_words"

    id = Column(Integer, primary_key=True, autoincrement=True)
    word = Column(String(100), unique=True, nullable=False, comment="违规词")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
