import cv2
import numpy as np
import os
from typing import Optional, Callable
from loguru import logger


class VideoProcessor:
    def __init__(self, source_type: str = "camera", source_addr: str = "", device_id: int = 0):
        self.source_type = source_type
        self.source_addr = source_addr
        self.device_id = device_id
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_running = False

    def _resolve_video_path(self, path: str) -> str:
        """解析视频文件路径，尝试多种可能的位置"""
        if not path:
            return path

        # 如果已经是绝对路径且存在，直接返回
        if os.path.isabs(path) and os.path.exists(path):
            return path

        # 尝试相对路径
        if os.path.exists(path):
            return path

        # 尝试 TEST/videodata 目录
        test_paths = [
            f"TEST/videodata/{path}",
            f"TEST/videodata/{os.path.basename(path)}",
            f"../TEST/videodata/{path}",
            f"../TEST/videodata/{os.path.basename(path)}",
        ]

        for test_path in test_paths:
            if os.path.exists(test_path):
                logger.info(f"Resolved video path: {path} -> {test_path}")
                return test_path

        # 如果都找不到，返回原始路径
        return path

    def start(self) -> bool:
        try:
            if self.source_type == "camera":
                self.cap = cv2.VideoCapture(self.device_id)
            elif self.source_type == "file":
                resolved_path = self._resolve_video_path(self.source_addr)
                self.cap = cv2.VideoCapture(resolved_path)
            elif self.source_type == "stream":
                self.cap = cv2.VideoCapture(self.source_addr)

            if not self.cap.isOpened():
                logger.error(f"Failed to open video source: {self.source_type} - {self.source_addr or self.device_id}")
                return False

            self.is_running = True
            logger.info(f"Video processor started: {self.source_type}")
            return True
        except Exception as e:
            logger.error(f"Error starting video processor: {e}")
            return False

    def stop(self):
        if self.cap:
            self.cap.release()
        self.is_running = False
        logger.info("Video processor stopped")

    def read_frame(self) -> Optional[np.ndarray]:
        if not self.is_running or not self.cap:
            return None

        ret, frame = self.cap.read()
        if not ret:
            if self.source_type == "camera":
                logger.warning("Camera disconnected")
                return None
            elif self.source_type == "file":
                # 本地视频文件播放完毕，自动停止
                logger.info("Video file finished playing")
                self.is_running = False
                return None
            return None

        return frame

    def process_frames(self, callback: Callable[[np.ndarray], None], fps: int = 10):
        import time
        frame_interval = 1.0 / fps

        while self.is_running:
            frame = self.read_frame()
            if frame is not None:
                callback(frame)

            time.sleep(frame_interval)
