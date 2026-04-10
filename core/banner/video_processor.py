import cv2
import numpy as np
import threading
import time
import uuid
import os
import io
from typing import Optional, Dict, Any, List
from datetime import datetime
from loguru import logger
from PIL import Image, ImageDraw, ImageFont
from queue import Queue

from core.video_processor import VideoProcessor
from core.banner.detector import banner_detector
from utils.rabbitmq_utils import mq_client
from utils.db_utils import get_db_session
from models.banner import AlarmBanner


class BannerVideoProcessor:
    QUEUE_NAME = "warning_banner"
    EVENT_ID = "01"
    OUTPUT_DIR = "output"

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
        self.video_writer = None
        self.show_window = False
        self.frame_queue = Queue(maxsize=2)
        self.stream_quality = 80
        self.output_video_path = None
        self.output_videos = []  # 保存所有生成的视频文件路径

    def _init_tracker(self):
        from core.banner.byte_tracker_wrapper import SimpleByteTracker

        self.tracker = SimpleByteTracker(
            track_thresh=0.3,
            track_buffer=30,
            match_thresh=0.8,
            frame_rate=30
        )

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

            # 获取视频属性
            width = int(self.video_processor.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.video_processor.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            video_fps = int(self.video_processor.cap.get(cv2.CAP_PROP_FPS))
            if video_fps <= 0:
                video_fps = fps

            # 为所有类型创建视频写入器（包括摄像头和流）
            os.makedirs(self.OUTPUT_DIR, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(self.OUTPUT_DIR, f"{source_id}_{timestamp}_detected.mp4")
            # 转换为绝对路径
            output_path = os.path.abspath(output_path)
            # 使用 avc1 编码器（H.264）- 浏览器原生支持
            # 注意：需要安装 OpenH264 编码器或系统支持 H.264
            fourcc = cv2.VideoWriter_fourcc(*'avc1')
            self.video_writer = cv2.VideoWriter(output_path, fourcc, video_fps, (width, height))
            self.output_video_path = output_path
            # 添加到视频列表
            if output_path not in self.output_videos:
                self.output_videos.append(output_path)
            logger.info(f"Output video will be saved to: {output_path}")

            # 注意：OpenCV 窗口显示与 FastAPI 后台线程有冲突
            # 实时显示功能暂时禁用，视频会保存到文件
            self.show_window = False

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
        logger.info("Stopping banner detection...")
        self.is_running = False

        # 先停止视频处理器（这会中断cap.read()阻塞）
        if self.video_processor:
            try:
                self.video_processor.stop()
            except Exception as e:
                logger.error(f"Error stopping video processor: {e}")

        # 等待检测线程结束
        if self.detection_thread and self.detection_thread.is_alive():
            try:
                self.detection_thread.join(timeout=3)
                if self.detection_thread.is_alive():
                    logger.warning("Detection thread did not stop in time")
            except Exception as e:
                logger.error(f"Error joining detection thread: {e}")

        # 释放视频写入器
        if self.video_writer:
            try:
                self.video_writer.release()
                logger.info("Output video saved")
            except Exception as e:
                logger.error(f"Error releasing video writer: {e}")
            finally:
                self.video_writer = None

        # 清空帧队列
        try:
            while not self.frame_queue.empty():
                self.frame_queue.get_nowait()
        except:
            pass

        self.yolo_model = None
        self.tracker = None
        self.ocr = None
        self.current_source_id = None
        self.current_source_type = None
        logger.info("Banner detection stopped")

    def _detection_loop(self, fps: int):
        frame_interval = 1.0 / fps
        frame_count = 0
        consecutive_none_count = 0
        completed_normally = False

        while self.is_running:
            try:
                frame = self.video_processor.read_frame()
                if frame is None:
                    # 检查是否是视频文件播放完毕
                    if self.current_source_type == "file" and not self.video_processor.is_running:
                        logger.info("Video file detection completed, stopping...")
                        completed_normally = True
                        break

                    consecutive_none_count += 1
                    # 如果连续30帧都读取失败，停止检测
                    if consecutive_none_count > 30:
                        logger.warning("Failed to read frame for 30 consecutive times, stopping detection")
                        break

                    time.sleep(frame_interval)
                    continue

                consecutive_none_count = 0
                frame_count += 1

                # 处理每一帧（添加检测框和标注）
                processed_frame = self._process_frame(frame)

                # 保存到视频文件
                if self.video_writer:
                    self.video_writer.write(processed_frame)

                # 将帧放入队列用于流式传输（只保留最新帧）
                if self.frame_queue.full():
                    try:
                        self.frame_queue.get_nowait()
                    except:
                        pass
                try:
                    self.frame_queue.put_nowait(processed_frame)
                except:
                    pass

                time.sleep(frame_interval)

            except Exception as e:
                logger.error(f"Error in detection loop: {e}")
                time.sleep(frame_interval)

        # 检测循环结束，确保资源被正确释放
        if completed_normally:
            logger.info("Detection loop completed normally, releasing resources...")
            self.stop_detection()

    def _process_frame(self, frame: np.ndarray) -> np.ndarray:
        """处理帧，绘制检测框和标注，返回处理后的帧"""
        try:
            banner_detector.clear_frame_state()

            results = self.yolo_model(frame, verbose=False)

            # 提取检测结果并转换为 ByteTrack 格式
            detections = []
            if results and results[0].boxes is not None:
                boxes = results[0].boxes.xyxy.cpu().numpy()
                confs = results[0].boxes.conf.cpu().numpy()

                for i in range(len(boxes)):
                    detections.append([
                        boxes[i][0], boxes[i][1], boxes[i][2], boxes[i][3], confs[i]
                    ])

            # ByteTrack 追踪
            tracked_objects = []
            if detections:
                tracked_objects = self.tracker.update(detections, frame)

            # 复制帧用于绘制
            processed_frame = frame.copy()
            frame_alerts = []

            for obj in tracked_objects:
                x1, y1, x2, y2 = int(obj.tlbr[0]), int(obj.tlbr[1]), int(obj.tlbr[2]), int(obj.tlbr[3])

                # 绘制追踪框
                cv2.rectangle(processed_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(processed_frame, f"ID:{obj.track_id}", (x1, y1 - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

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

                                    # 绘制违规标记（红色框）
                                    cv2.rectangle(processed_frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
                                    label = f"违规: {illegal_word}"
                                    self._draw_chinese_text(processed_frame, label, (x1, y1 - 30),
                                                           0.7, (255, 255, 255), (0, 0, 255))

                                    frame_alerts.append({
                                        'bbox': [x1, y1, x2, y2],
                                        'text': text,
                                        'illegal_word': illegal_word,
                                        'track_id': obj.track_id
                                    })

            return processed_frame

        except Exception as e:
            logger.error(f"Error processing frame: {e}")
            return frame

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

    def generate_mjpeg_stream(self):
        """生成MJPEG视频流"""
        empty_count = 0
        while self.is_running or not self.frame_queue.empty():
            try:
                if not self.frame_queue.empty():
                    frame = self.frame_queue.get()
                    empty_count = 0
                    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, self.stream_quality])
                    frame_bytes = buffer.tobytes()
                    yield (
                        b'--frame\r\n'
                        b'Content-Type: image/jpeg\r\n'
                        b'Content-Length: ' + str(len(frame_bytes)).encode() + b'\r\n'
                        b'\r\n' + frame_bytes + b'\r\n'
                    )
                else:
                    empty_count += 1
                    # 如果队列为空超过300次（约10秒）且检测已停止，退出循环
                    if empty_count > 300 and not self.is_running:
                        logger.info("Stream generator exiting: no frames and detection stopped")
                        break
                    time.sleep(0.033)
            except Exception as e:
                logger.error(f"Error generating stream: {e}")
                time.sleep(0.1)
        logger.info("MJPEG stream generator stopped")


banner_processor = BannerVideoProcessor()