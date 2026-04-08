import cv2
import numpy as np
import threading
import time
import uuid
import os
from typing import Optional, Dict, Any, List
from datetime import datetime
from loguru import logger
from PIL import Image, ImageDraw, ImageFont

from core.video_processor import VideoProcessor
from core.banner.detector import banner_detector
from utils.rabbitmq_utils import mq_client
from utils.db_utils import get_db_session
from models.banner import AlarmBanner


class BannerVideoProcessor:
    QUEUE_NAME = "warning_banner"
    EVENT_ID = "01"

    def __init__(self):
        self.video_processor: Optional[VideoProcessor] = None
        self.is_running = False
        self.detection_thread: Optional[threading.Thread] = None
        self.current_source_id: Optional[str] = None
        self.current_source_type: Optional[str] = None
        self.alarm_history: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()
        self.yolo_model = None
        self.tracker = None
        self.ocr = None

    def _init_tracker(self):
        from ultralytics import YOLO
        from trackers import BYTETracker

        class ByteTrackConfig:
            track_thresh = 0.3
            track_buffer = 30
            match_thresh = 0.8
            frame_rate = 30

        self.tracker = BYTETracker(ByteTrackConfig())

    def _init_ocr(self):
        from paddleocr import PaddleOCR
        self.ocr = PaddleOCR(lang='ch')
        logger.info("PaddleOCR initialized")

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
                logger.warning("Banner detection is already running")
                return False

            weights_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "weights", "banner.pt"
            )

            if not os.path.exists(weights_path):
                logger.error(f"Banner model not found: {weights_path}")
                return False

            logger.info(f"Loading banner model from: {weights_path}")
            from ultralytics import YOLO
            self.yolo_model = YOLO(weights_path)
            logger.info("Banner model loaded successfully")

            self._init_tracker()
            self._init_ocr()

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

            logger.info(f"Banner detection started: {source_type} - {source_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to start banner detection: {e}")
            return False

    def stop_detection(self):
        self.is_running = False

        if self.detection_thread and self.detection_thread.is_alive():
            self.detection_thread.join(timeout=5)

        if self.video_processor:
            self.video_processor.stop()

        self.yolo_model = None
        self.tracker = None
        self.ocr = None
        self.current_source_id = None
        self.current_source_type = None
        logger.info("Banner detection stopped")

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
            banner_detector.clear_frame_state()

            results = self.yolo_model(frame, verbose=False)

            detections = []
            if results and results[0].boxes is not None:
                boxes = results[0].boxes.xyxy.cpu().numpy()
                confs = results[0].boxes.conf.cpu().numpy()

                for i in range(len(boxes)):
                    detections.append([
                        boxes[i][0], boxes[i][1], boxes[i][2], boxes[i][3], confs[i]
                    ])

            tracked_objects = []
            if detections:
                import numpy as np
                detections_array = np.array(detections)
                tracked_objects = self.tracker.update(detections_array, frame)

            frame_alerts = []

            for obj in tracked_objects:
                x1, y1, x2, y2 = int(obj.tlbr[0]), int(obj.tlbr[1]), int(obj.tlbr[2]), int(obj.tlbr[3])

                roi = frame[y1:y2, x1:x2]
                if roi.size == 0:
                    continue

                processed_roi = self._preprocess_roi(roi)

                try:
                    ocr_result = self.ocr.predict(processed_roi)
                except:
                    continue

                if ocr_result and isinstance(ocr_result, list):
                    for item in ocr_result:
                        if item is None or not isinstance(item, dict):
                            continue

                        rec_texts = item.get('rec_texts', [])
                        rec_scores = item.get('rec_scores', [])

                        for text, text_conf in zip(rec_texts, rec_scores):
                            if text_conf < 0.3 or not text.strip():
                                continue

                            is_illegal, illegal_word = banner_detector.check_illegal(text)

                            if is_illegal:
                                current_time = datetime.now()
                                track_id = str(obj.track_id)

                                if banner_detector.should_alert(track_id, text, current_time):
                                    banner_detector.record_alert(track_id, text, illegal_word, current_time)
                                    self._send_banner_alarm(track_id, text, illegal_word, x1, y1, x2, y2)

                                    frame_alerts.append({
                                        'bbox': [x1, y1, x2, y2],
                                        'text': text,
                                        'illegal_word': illegal_word,
                                        'track_id': obj.track_id
                                    })

        except Exception as e:
            logger.error(f"Error processing frame: {e}")

    def _preprocess_roi(self, roi, max_side=1000):
        height, width = roi.shape[:2]

        if height < 10 or width < 10:
            return roi

        if height > max_side or width > max_side:
            scale = max_side / max(height, width)
            roi = cv2.resize(roi, (int(width * scale), int(height * scale)))

        return roi

    def _draw_chinese_text(self, frame, text, position, font_scale=0.7, text_color=(255, 255, 255), bg_color=None):
        x, y = position

        pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img)

        font_size = int(25 * font_scale)

        try:
            font = ImageFont.truetype("msyh.ttc", font_size)
        except:
            try:
                font = ImageFont.truetype("simsun.ttc", font_size)
            except:
                font = ImageFont.load_default()

        bbox = draw.textbbox((x, y), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        if bg_color is not None:
            draw.rectangle(
                [x, y - text_height - 2, x + text_width + 2, y + 2],
                fill=bg_color
            )

        draw.text((x, y - text_height), text, fill=text_color, font=font)

        frame[:, :, :] = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

        return frame

    def _send_banner_alarm(
        self,
        track_id: str,
        text: str,
        illegal_word: str,
        x1: int,
        y1: int,
        x2: int,
        y2: int
    ):
        try:
            message_id = str(uuid.uuid4())
            current_time = datetime.now()

            alarm_message = {
                "alarm_time": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                "event_id": self.EVENT_ID,
                "alarm_type": "横幅违规告警",
                "content": {
                    "track_id": track_id,
                    "detected_text": text,
                    "illegal_word": illegal_word,
                    "bbox": [int(x1), int(y1), int(x2), int(y2)],
                    "source_type": self.current_source_type,
                    "source_id": self.current_source_id
                },
                "message_id": message_id
            }

            mq_client.publish(self.QUEUE_NAME, alarm_message)
            self._save_alarm_to_db(alarm_message)

            logger.info(f"Banner alarm sent: track_id={track_id}, illegal_word={illegal_word}, text={text}")

        except Exception as e:
            logger.error(f"Error sending banner alarm: {e}")

    def _save_alarm_to_db(self, alarm_message: dict):
        try:
            db = get_db_session()
            try:
                alarm = AlarmBanner(
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


banner_processor = BannerVideoProcessor()