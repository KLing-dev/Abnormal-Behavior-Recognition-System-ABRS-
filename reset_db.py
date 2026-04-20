#!/usr/bin/env python
"""重置数据库表结构"""
import sys
sys.path.insert(0, '.')

from models.base import engine
from models.absent import Base

print("正在删除旧表...")
Base.metadata.drop_all(bind=engine)
print("旧表已删除")

print("正在创建新表...")
Base.metadata.create_all(bind=engine)
print("新表已创建，包含 face_img 和 face_detection_box 字段")
