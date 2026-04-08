import cv2
import numpy as np
import threading
import time
import uuid
import os
from typing import Optional, Dict, Any, Callable
from datetime import datetime
from loguru import logger
from ultralytics import YOLO

from core.video_processor import VideoProcessor
from core.gathering.detector import gathering_detector
from utils.rabbitmq_utils import mq_client
from utils.db_utils import get_db_session
from models.gathering import AlarmGathering


class GatheringVideoProcessor:
    """聚集检测视频处理器"""

    QUEUE_NAME = "warning_gathering"
    EVENT_ID = "04"

    def __init__(self):
        self.video_processor: Optional[VideoProcessor] = None
        self.is_running = False
        self.detection_thread: Optional[threading.Thread] = None
        self.current_source_id: Optional[str] = None
        self.current_source_type: Optional[str] = None
        self.alarm_history: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()
        self.yolo_model: Optional[YOLO] = None

    def start_detection(
        self,
        source_type: str,
        source_id: str,
        source_addr: str = "",
        device_id: int = 0,
        fps: int = 10
    ) -> bool:
        """启动聚集检测"""
        try:
            if self.is_running:
                logger.warning("Gathering detection is already running")
                return False

            weights_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "weights", "yolov12n.pt"
            )

            if not os.path.exists(weights_path):
                logger.error(f"YOLO model not found: {weights_path}")
                return False

            logger.info(f"Loading YOLO model from: {weights_path}")
            self.yolo_model = YOLO(weights_path)
            logger.info("YOLO model loaded successfully")

            self.video_processor = VideoProcessor(
                source_type=source_type,
                source_addr=source_addr,
                device_id=device_id
            )

            if not self.video_processor.start():
                return False

            self.current_source_id = source_id
            self.current_source_type = source_type
            self.is_running = True

            self.detection_thread = threading.Thread(
                target=self._detection_loop,
                args=(fps,),
                daemon=True
            )
            self.detection_thread.start()

            logger.info(f"Gathering detection started: {source_type} - {source_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to start gathering detection: {e}")
            return False

    def stop_detection(self):
        """停止聚集检测"""
        self.is_running = False

        if self.detection_thread and self.detection_thread.is_alive():
            self.detection_thread.join(timeout=5)

        if self.video_processor:
            self.video_processor.stop()

        self.yolo_model = None
        self.current_source_id = None
        self.current_source_type = None
        logger.info("Gathering detection stopped")

    def _detection_loop(self, fps: int):
        """检测主循环"""
        frame_interval = 1.0 / fps
        frame_count = 0

        while self.is_running:
            try:
                frame = self.video_processor.read_frame()
                if frame is None:
                    time.sleep(frame_interval)
                    continue

                frame_count += 1

                # 每秒处理一次（根据fps）
                if frame_count % fps == 0:
                    self._process_frame(frame)

                time.sleep(frame_interval)

            except Exception as e:
                logger.error(f"Error in detection loop: {e}")
                time.sleep(frame_interval)

    def _process_frame(self, frame: np.ndarray):
        """处理单帧图像"""
        try:
            for area_id in gathering_detector.areas.keys():
                person_count = self._detect_persons_in_area(frame, area_id)
                self._check_area_gathering(area_id, person_count)

        except Exception as e:
            logger.error(f"Error processing frame: {e}")

    def _detect_persons_in_area(self, frame: np.ndarray, area_id: str) -> int:
        """使用YOLO检测指定区域内的人员数量"""
        if self.yolo_model is None:
            logger.warning("YOLO model not initialized, returning 0")
            return 0

        try:
            coords = gathering_detector.get_area_coords(area_id)
            if not coords:
                return 0

            x1, y1, x2, y2 = coords

            results = self.yolo_model(frame, verbose=False)
            person_count = 0
            for result in results:
                boxes = result.boxes
                for box in boxes:
                    cls = int(box.cls[0])
                    if cls == 0:
                        bx1, by1, bx2, by2 = map(int, box.xyxy[0])
                        box_center_x = (bx1 + bx2) // 2
                        box_center_y = (by1 + by2) // 2
                        if x1 <= box_center_x <= x2 and y1 <= box_center_y <= y2:
                            person_count += 1
            return person_count
        except Exception as e:
            logger.error(f"Error detecting persons in area {area_id}: {e}")
            return 0

    def _check_area_gathering(self, area_id: str, total_count: int):
        """检查指定区域的聚集情况"""
        try:
            # 更新人数到缓存
            gathering_detector.update_person_count(area_id, total_count)

            # 检查聚集状态
            level, duration_min = gathering_detector.check_gathering(area_id)

            if level and duration_min >= 3:
                # 触发聚集告警
                self._send_gathering_alarm(area_id, total_count, level, duration_min)
            elif not level:
                # 检查是否需要发送解除告警
                self._check_clear_alarm(area_id)

        except Exception as e:
            logger.error(f"Error checking area {area_id}: {e}")

    def _send_gathering_alarm(self, area_id: str, count: int, level: str, duration_min: float):
        """发送聚集告警"""
        try:
            alarm_key = f"{area_id}_{level}"
            current_time = datetime.now()

            with self.lock:
                # 检查是否已经发送过相同等级的告警
                if alarm_key in self.alarm_history:
                    last_alarm = self.alarm_history[alarm_key]
                    time_diff = (current_time - last_alarm["time"]).total_seconds()
                    if time_diff < 300:  # 5分钟内不重复发送相同等级告警
                        return

                # 构建告警消息
                message_id = str(uuid.uuid4())
                thresholds = gathering_detector.get_level_thresholds(area_id)

                alarm_message = {
                    "alarm_time": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "event_id": self.EVENT_ID,
                    "alarm_type": "聚集告警",
                    "content": {
                        "area_id": area_id,
                        "gathering_count": count,
                        "level": level,
                        "level_thresholds": thresholds,
                        "duration_min": round(duration_min, 1),
                        "source_type": self.current_source_type,
                        "source_id": self.current_source_id
                    },
                    "message_id": message_id
                }

                # 发送到RabbitMQ
                mq_client.publish(self.QUEUE_NAME, alarm_message)

                # 保存到数据库
                self._save_alarm_to_db(alarm_message)

                # 更新告警历史
                self.alarm_history[alarm_key] = {
                    "time": current_time,
                    "level": level,
                    "count": count
                }

                logger.info(f"Gathering alarm sent: {area_id} - {level} - {count}人")

        except Exception as e:
            logger.error(f"Error sending gathering alarm: {e}")

    def _check_clear_alarm(self, area_id: str):
        """检查并发送解除告警"""
        try:
            # 查找该区域之前的告警记录
            clear_needed = False
            for key in list(self.alarm_history.keys()):
                if key.startswith(f"{area_id}_"):
                    clear_needed = True
                    del self.alarm_history[key]

            if clear_needed:
                current_time = datetime.now()
                message_id = str(uuid.uuid4())

                clear_message = {
                    "alarm_time": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "event_id": self.EVENT_ID,
                    "alarm_type": "聚集告警解除",
                    "content": {
                        "area_id": area_id,
                        "gathering_count": 0,
                        "level": None,
                        "alarm_end": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "source_type": self.current_source_type,
                        "source_id": self.current_source_id
                    },
                    "message_id": message_id
                }

                # 发送到RabbitMQ
                mq_client.publish(self.QUEUE_NAME, clear_message)

                # 保存到数据库
                self._save_alarm_to_db(clear_message)

                # 清除区域状态
                gathering_detector.clear_area_state(area_id)

                logger.info(f"Gathering clear alarm sent: {area_id}")

        except Exception as e:
            logger.error(f"Error sending clear alarm: {e}")

    def _save_alarm_to_db(self, alarm_message: dict):
        """保存告警到数据库"""
        try:
            db = get_db_session()
            try:
                alarm = AlarmGathering(
                    alarm_time=datetime.strptime(alarm_message["alarm_time"], "%Y-%m-%d %H:%M:%S"),
                    event_id=alarm_message["event_id"],
                    alarm_type=alarm_message["alarm_type"],
                    content=alarm_message["content"],
                    source_type=alarm_message["content"]["source_type"],
                    source_id=alarm_message["content"]["source_id"],
                    message_id=alarm_message["message_id"]
                )
                db.add(alarm)
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error saving alarm to DB: {e}")


# 全局处理器实例
gathering_processor = GatheringVideoProcessor()
