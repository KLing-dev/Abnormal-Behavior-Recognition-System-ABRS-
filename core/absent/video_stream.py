"""
离岗检测视频流处理器
支持摄像头/视频文件/网络流三种输入源
"""
import cv2
import threading
import time
import uuid
from typing import Optional, Callable, Dict
from datetime import datetime
from utils.rabbitmq_utils import mq_client as rabbitmq_client
from core.absent.detector import absent_detector


class VideoStreamProcessor:
    """视频流处理器"""
    
    def __init__(self):
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_running = False
        self.thread: Optional[threading.Thread] = None
        self.source_id: Optional[str] = None
        self.source_type: Optional[str] = None
        self.frame_callback: Optional[Callable] = None
        self.alarm_callback: Optional[Callable] = None
        self.fps = 10  # 默认帧率
        self.frame_interval = 1.0 / self.fps
        
    def open_source(self, source_type: str, source_id: str, 
                   device_id: int = 0, source_addr: Optional[str] = None) -> bool:
        """打开视频源"""
        self.source_id = source_id
        self.source_type = source_type
        
        if source_type == "camera":
            self.cap = cv2.VideoCapture(device_id)
            # 设置分辨率
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
            self.cap.set(cv2.CAP_PROP_FPS, self.fps)
        elif source_type == "file":
            if not source_addr:
                print("错误: 文件类型需要提供source_addr")
                return False
            self.cap = cv2.VideoCapture(source_addr)
        elif source_type == "stream":
            if not source_addr:
                print("错误: 流类型需要提供source_addr")
                return False
            self.cap = cv2.VideoCapture(source_addr)
        else:
            print(f"错误: 不支持的源类型 {source_type}")
            return False
        
        if not self.cap.isOpened():
            print(f"错误: 无法打开视频源 {source_id}")
            return False
        
        print(f"成功打开视频源: {source_id} ({source_type})")
        return True
    
    def close_source(self):
        """关闭视频源"""
        if self.cap:
            self.cap.release()
            self.cap = None
        print("视频源已关闭")
    
    def set_frame_callback(self, callback: Callable):
        """设置帧处理回调函数"""
        self.frame_callback = callback
    
    def set_alarm_callback(self, callback: Callable):
        """设置告警回调函数"""
        self.alarm_callback = callback
    
    def _process_loop(self):
        """视频处理主循环"""
        frame_count = 0
        last_time = time.time()
        
        while self.is_running and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            
            if not ret:
                # 视频文件结束或流断开
                if self.source_type == "file":
                    print("视频文件播放结束")
                    break
                else:
                    # 尝试重连
                    print("视频流断开，尝试重连...")
                    time.sleep(1)
                    continue
            
            frame_count += 1
            current_time = time.time()
            
            # 控制帧率
            elapsed = current_time - last_time
            if elapsed < self.frame_interval:
                time.sleep(self.frame_interval - elapsed)
            last_time = current_time
            
            # 处理帧
            if self.frame_callback:
                try:
                    alarms = self.frame_callback(frame)
                    
                    # 处理告警
                    if alarms and self.alarm_callback:
                        for alarm in alarms:
                            self.alarm_callback(alarm)
                except Exception as e:
                    print(f"帧处理错误: {e}")
        
        self.is_running = False
        print("视频处理循环结束")
    
    def start(self):
        """启动视频处理"""
        if not self.cap or not self.cap.isOpened():
            print("错误: 视频源未打开")
            return False
        
        self.is_running = True
        self.thread = threading.Thread(target=self._process_loop)
        self.thread.daemon = True
        self.thread.start()
        print("视频处理已启动")
        return True
    
    def stop(self):
        """停止视频处理"""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=2)
        self.close_source()
        print("视频处理已停止")
    
    def get_frame_size(self) -> tuple:
        """获取视频帧尺寸"""
        if self.cap:
            width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            return (width, height)
        return (0, 0)
    
    def get_fps(self) -> float:
        """获取视频帧率"""
        if self.cap:
            return self.cap.get(cv2.CAP_PROP_FPS)
        return 0.0


class AbsentStreamManager:
    """离岗检测流管理器"""
    
    def __init__(self):
        self.processor = VideoStreamProcessor()
        self.is_detecting = False
        self.db_session = None
        
    def start_detection(self, source_type: str, source_id: str,
                       db_session, device_id: int = 0, 
                       source_addr: Optional[str] = None) -> bool:
        """启动离岗检测"""
        # 保存数据库会话
        self.db_session = db_session
        
        # 加载人员配置
        absent_detector.load_persons_from_db(db_session)
        
        # 打开视频源
        if not self.processor.open_source(source_type, source_id, device_id, source_addr):
            return False
        
        # 设置回调函数
        self.processor.set_frame_callback(absent_detector.process_frame)
        self.processor.set_alarm_callback(self._handle_alarm)
        
        # 启动检测器
        absent_detector.start_detection(source_id, source_type)
        
        # 启动视频处理
        if self.processor.start():
            self.is_detecting = True
            return True
        
        return False
    
    def stop_detection(self):
        """停止离岗检测"""
        self.processor.stop()
        absent_detector.stop_detection()
        self.is_detecting = False
    
    def _handle_alarm(self, alarm: Dict):
        """处理告警"""
        try:
            # 构建告警消息
            message = {
                "alarm_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "event_id": "02",
                "alarm_type": alarm["type"],
                "content": alarm["content"],
                "message_id": str(uuid.uuid4())
            }
            
            # 发送到RabbitMQ
            try:
                rabbitmq_client.publish(
                    queue_name="warning_absent",
                    message=message
                )
            except Exception as mq_error:
                print(f"RabbitMQ发送失败（非关键）: {mq_error}")
            
            # 保存到数据库
            if self.db_session:
                from models.absent import AlarmAbsent
                db_alarm = AlarmAbsent(
                    alarm_time=datetime.now(),
                    event_id="02",
                    alarm_type=alarm["type"],
                    content=alarm["content"],
                    source_type=alarm["content"].get("source_type", "camera"),
                    source_id=alarm["content"].get("source_id", ""),
                    message_id=message["message_id"],
                    status=0
                )
                self.db_session.add(db_alarm)
                self.db_session.commit()
                print(f"告警已保存到数据库: {alarm['type']} - {alarm['content'].get('person_id', '')}")
            else:
                print(f"警告: 无数据库会话，告警未保存: {alarm['type']}")
            
        except Exception as e:
            print(f"处理告警失败: {e}")
            import traceback
            traceback.print_exc()
    
    def get_status(self) -> Dict:
        """获取检测状态"""
        return {
            "is_detecting": self.is_detecting,
            "stream_status": absent_detector.get_status()
        }


# 全局流管理器实例
stream_manager = AbsentStreamManager()
