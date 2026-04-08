"""
聚集检测模块

提供人员聚集检测功能，包括：
- GatheringDetector: 聚集检测器核心类
- GatheringVideoProcessor: 聚集视频处理器
"""

from core.gathering.detector import gathering_detector, GatheringDetector
from core.gathering.video_processor import gathering_processor, GatheringVideoProcessor

__all__ = [
    "gathering_detector",
    "GatheringDetector",
    "gathering_processor",
    "GatheringVideoProcessor",
]
