import cv2
import numpy as np
from typing import Optional, Callable
from loguru import logger


class VideoProcessor:
    def __init__(self, source_type: str = "camera", source_addr: str = "", device_id: int = 0):
        self.source_type = source_type
        self.source_addr = source_addr
        self.device_id = device_id
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_running = False

    def start(self) -> bool:
        try:
            if self.source_type == "camera":
                self.cap = cv2.VideoCapture(self.device_id)
            elif self.source_type == "file":
                self.cap = cv2.VideoCapture(self.source_addr)
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
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
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
