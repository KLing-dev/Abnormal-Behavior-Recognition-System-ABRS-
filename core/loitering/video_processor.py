import cv2
import numpy as np
import threading
import time
import uuid
import os
from typing import Optional, Dict, Any, Set
from datetime import datetime
from loguru import logger
from ultralytics import YOLO

from core.video_processor import VideoProcessor
from core.loitering.detector import loitering_detector
from utils.rabbitmq_utils import mq_client
from utils.db_utils import get_db_session
from models.loitering import AlarmLoitering


class LoiteringVideoProcessor:
    QUEUE_NAME = "warning_loitering"
    EVENT_ID = "03"

    def __init__(self):
        self.video_processor: Optional[VideoProcessor] = None
        self.is_running = False
        self.detection_thread: Optional[threading.Thread] = None
        self.current_source_id: Optional[str] = None
        self.current_source_type: Optional[str] = None
        self.alarm_history: Dict[str, Dict[str, Any]] = {}
        self.active_tracks: Dict[str, Set[str]] = {}
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
        try:
            if self.is_running:
                logger.warning("Loitering detection is already running")
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

            logger.info(f"Loitering detection started: {source_type} - {source_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to start loitering detection: {e}")
            return False

    def stop_detection(self):
        self.is_running = False

        if self.detection_thread and self.detection_thread.is_alive():
            self.detection_thread.join(timeout=5)

        if self.video_processor:
            self.video_processor.stop()

        self.yolo_model = None
        self.current_source_id = None
        self.current_source_type = None
        self.active_tracks.clear()
        logger.info("Loitering detection stopped")

    def _detection_loop(self, fps: int):
        frame_interval = 1.0 / fps
        frame_count = 0

        while self.is_running:
            try:
                frame = self.video_processor.read_frame()
                if frame is None:
                    time.sleep(frame_interval)
                    continue

                frame_count += 1

                if frame_count % fps == 0:
                    self._process_frame(frame)

                time.sleep(frame_interval)

            except Exception as e:
                logger.error(f"Error in detection loop: {e}")
                time.sleep(frame_interval)

    def _process_frame(self, frame: np.ndarray):
        try:
            for area_id in loitering_detector.areas.keys():
                self._track_and_detect(frame, area_id)

        except Exception as e:
            logger.error(f"Error processing frame: {e}")

    def _track_and_detect(self, frame: np.ndarray, area_id: str):
        if self.yolo_model is None:
            return

        try:
            coords = loitering_detector.get_area_coords(area_id)
            if not coords:
                return

            x1, y1, x2, y2 = coords

            results = self.yolo_model.track(frame, persist=True, verbose=False)

            current_tracks_in_area = set()
            current_tracks_all = set()

            for result in results:
                for box in result.boxes:
                    if int(box.cls[0]) == 0:
                        bx1, by1, bx2, by2 = map(int, box.xyxy[0])
                        box_center_x = (bx1 + bx2) // 2
                        box_center_y = (by1 + by2) // 2

                        if box.id is not None:
                            track_id = str(int(box.id[0]))
                            current_tracks_all.add(track_id)

                            if x1 <= box_center_x <= x2 and y1 <= box_center_y <= y2:
                                current_tracks_in_area.add(track_id)
                                loitering_detector.update_duration(area_id, track_id)

            if area_id not in self.active_tracks:
                self.active_tracks[area_id] = set()

            departed_tracks = self.active_tracks[area_id] - current_tracks_in_area
            for track_id in departed_tracks:
                loitering_detector.mark_person_left(area_id, track_id)

            self.active_tracks[area_id] = current_tracks_in_area

            self._check_and_send_alarm(area_id, current_tracks_in_area)

        except Exception as e:
            logger.error(f"Error tracking in area {area_id}: {e}")

    def _check_and_send_alarm(self, area_id: str, current_tracks_in_area: Set[str]):
        try:
            loitering_tracks = loitering_detector.check_loitering(area_id)
            loitering_count = len(loitering_tracks)
            threshold_min = loitering_detector.get_threshold(area_id)

            alarm_key = f"{area_id}_{loitering_count}"
            current_time = datetime.now()

            if loitering_count > 0:
                with self.lock:
                    last_count = self.alarm_history.get(area_id, {}).get("count", 0)

                    if last_count != loitering_count:
                        self._send_loitering_alarm(area_id, loitering_count, threshold_min, loitering_tracks)
                        self.alarm_history[area_id] = {
                            "time": current_time,
                            "count": loitering_count
                        }
            else:
                with self.lock:
                    if area_id in self.alarm_history:
                        last_alarm_time = self.alarm_history[area_id].get("time")
                        if last_alarm_time and (current_time - last_alarm_time).total_seconds() >= 300:
                            self._send_clear_alarm(area_id)
                            del self.alarm_history[area_id]

        except Exception as e:
            logger.error(f"Error checking alarm for area {area_id}: {e}")

    def _send_loitering_alarm(self, area_id: str, loitering_count: int, threshold_min: int, loitering_tracks: list):
        try:
            message_id = str(uuid.uuid4())
            current_time = datetime.now()

            alarm_message = {
                "alarm_time": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                "event_id": self.EVENT_ID,
                "alarm_type": "徘徊告警",
                "content": {
                    "area_id": area_id,
                    "loitering_count": loitering_count,
                    "threshold_min": threshold_min,
                    "current_duration_min": threshold_min,
                    "source_type": self.current_source_type,
                    "source_id": self.current_source_id
                },
                "message_id": message_id
            }

            mq_client.publish(self.QUEUE_NAME, alarm_message)
            self._save_alarm_to_db(alarm_message)

            logger.info(f"Loitering alarm sent: {area_id} - {loitering_count} persons loitering")

        except Exception as e:
            logger.error(f"Error sending loitering alarm: {e}")

    def _send_clear_alarm(self, area_id: str):
        try:
            message_id = str(uuid.uuid4())
            current_time = datetime.now()

            clear_message = {
                "alarm_time": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                "event_id": self.EVENT_ID,
                "alarm_type": "徘徊告警解除",
                "content": {
                    "area_id": area_id,
                    "loitering_count": 0,
                    "alarm_end": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "source_type": self.current_source_type,
                    "source_id": self.current_source_id
                },
                "message_id": message_id
            }

            mq_client.publish(self.QUEUE_NAME, clear_message)
            self._save_alarm_to_db(clear_message)
            loitering_detector.clear_area_state(area_id)

            logger.info(f"Loitering clear alarm sent: {area_id}")

        except Exception as e:
            logger.error(f"Error sending clear alarm: {e}")

    def _save_alarm_to_db(self, alarm_message: dict):
        try:
            db = get_db_session()
            try:
                alarm = AlarmLoitering(
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


loitering_processor = LoiteringVideoProcessor()
