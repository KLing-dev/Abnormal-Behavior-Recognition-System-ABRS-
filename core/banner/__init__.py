"""
横幅检测模块

提供横幅检测与违规词识别功能，包括：
- BannerDetector: 横幅检测器核心类
- BannerVideoProcessor: 横幅视频处理器
"""

from core.banner.detector import banner_detector, BannerDetector
from core.banner.video_processor import banner_processor, BannerVideoProcessor

__all__ = [
    "banner_detector",
    "BannerDetector",
    "banner_processor",
    "BannerVideoProcessor",
]