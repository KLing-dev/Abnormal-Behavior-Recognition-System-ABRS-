"""
离岗检测器 - 核心检测逻辑
基于面部识别实现人员在岗/离岗状态监测
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, time
from enum import Enum
import uuid
from utils.redis_utils import redis_client
from core.absent.face_recognition import face_recognizer


class AbsentStatus(Enum):
    """离岗状态枚举"""
    ON_DUTY = "在岗"
    ABSENT = "离岗"
    RETURNED = "回岗"


class AbsentDetector:
    """离岗检测器"""
    
    # Redis缓存键
    CACHE_KEY_PERSON_CONFIG = "abrs:absent:person:config"
    CACHE_KEY_TIMER = "abrs:absent:timer:{person_id}"
    CACHE_KEY_ALARM_LIMIT = "abrs:absent:alarm:limit:{person_id}"
    CACHE_KEY_ALARM_STATE = "abrs:absent:alarm_state:{person_id}"
    
    # 缓存过期时间
    CACHE_EXPIRE_STATIC = 300  # 5分钟
    CACHE_EXPIRE_DYNAMIC = 3600  # 1小时（计时器需要足够长）
    CACHE_EXPIRE_ALARM_LIMIT = 300  # 5分钟限流
    
    # 防抖配置
    ABSENT_CONFIRM_FRAMES = 3  # 连续3帧未检测到才判定为离岗
    PRESENT_CONFIRM_FRAMES = 2  # 连续2帧检测到才判定为在岗
    
    def __init__(self):
        self.persons: Dict[str, Any] = {}  # 人员配置
        self.person_status: Dict[str, AbsentStatus] = {}  # 人员状态
        self.absent_start_time: Dict[str, datetime] = {}  # 离岗开始时间
        self.last_alarm_time: Dict[str, datetime] = {}  # 上次告警时间
        self.is_running = False
        self.source_id: Optional[str] = None
        self.source_type: Optional[str] = None
        
        # 防抖计数器
        self.missed_frame_count: Dict[str, int] = {}  # 未检测到的连续帧数
        self.matched_frame_count: Dict[str, int] = {}  # 检测到的连续帧数
        
    def load_persons_from_db(self, db_session):
        """从数据库加载人员配置"""
        from models.absent import Person
        
        persons = db_session.query(Person).all()
        for person in persons:
            self.persons[person.person_id] = {
                "person_id": person.person_id,
                "name": person.name,
                "post": person.post,
                "duty_period": person.duty_period,
                "max_absent_min": person.max_absent_min,
                "face_feature": person.face_feature
            }
            # 加载面部特征
            if person.face_feature:
                face_recognizer.load_person_feature(person.person_id, person.face_feature)
        
        # 缓存到Redis
        redis_client.set(self.CACHE_KEY_PERSON_CONFIG, list(self.persons.values()), 
                        ex=self.CACHE_EXPIRE_STATIC)
        
    def load_persons_from_cache(self):
        """从缓存加载人员配置"""
        cached = redis_client.get(self.CACHE_KEY_PERSON_CONFIG)
        if cached:
            import json
            persons_list = json.loads(cached) if isinstance(cached, str) else cached
            for person in persons_list:
                self.persons[person["person_id"]] = person
                if person.get("face_feature"):
                    face_recognizer.load_person_feature(person["person_id"], 
                                                       person["face_feature"])
    
    def is_in_duty_period(self, duty_period: str) -> bool:
        """检查当前是否在站岗时间段内"""
        try:
            start_str, end_str = duty_period.split("-")
            now = datetime.now().time()
            start = time(int(start_str[:2]), int(start_str[3:5]))
            end = time(int(end_str[:2]), int(end_str[3:5]))
            return start <= now <= end
        except Exception as e:
            print(f"解析站岗时间段失败: {e}")
            return False
    
    def update_absent_timer(self, person_id: str) -> float:
        """更新离岗计时器 - 基于真实时间"""
        key = self.CACHE_KEY_TIMER.format(person_id=person_id)
        start_key = f"abrs:absent:timer_start:{person_id}"
        
        # 获取离岗开始时间
        start_time_str = redis_client.get(start_key)
        if start_time_str:
            start_time = datetime.fromisoformat(start_time_str)
        else:
            start_time = datetime.now()
            redis_client.set(start_key, start_time.isoformat(), ex=self.CACHE_EXPIRE_DYNAMIC)
        
        # 计算实际离岗时长（秒）
        current = (datetime.now() - start_time).total_seconds()
        
        # 更新Redis
        redis_client.set(key, current, ex=self.CACHE_EXPIRE_DYNAMIC)
        
        # 更新内存状态
        self.absent_start_time[person_id] = start_time
        
        return current
    
    def reset_absent_timer(self, person_id: str):
        """重置离岗计时器"""
        key = self.CACHE_KEY_TIMER.format(person_id=person_id)
        start_key = f"abrs:absent:timer_start:{person_id}"
        redis_client.delete(key)
        redis_client.delete(start_key)
        self.absent_start_time.pop(person_id, None)
    
    def get_absent_duration(self, person_id: str) -> float:
        """获取离岗时长（秒）"""
        key = self.CACHE_KEY_TIMER.format(person_id=person_id)
        duration = redis_client.get(key)
        return float(duration) if duration else 0
    
    def check_should_alarm(self, person_id: str) -> tuple[bool, str, Dict]:
        """检查是否应该触发告警"""
        person = self.persons.get(person_id)
        if not person:
            return False, "", {}
        
        # 检查是否在站岗时间
        if not self.is_in_duty_period(person["duty_period"]):
            return False, "", {}
        
        absent_seconds = self.get_absent_duration(person_id)
        max_absent_min = float(person["max_absent_min"])
        
        # 转换为秒进行比较（支持小数分钟）
        max_absent_sec = max_absent_min * 60
        
        print(f"[DEBUG] Check alarm: person={person_id}, absent={absent_seconds:.1f}s, threshold={max_absent_sec:.1f}s")
        
        # 检查是否达到离岗阈值
        if absent_seconds >= max_absent_sec:
            # 检查是否是首次告警
            alarm_state_key = self.CACHE_KEY_ALARM_STATE.format(person_id=person_id)
            alarm_state = redis_client.get(alarm_state_key)
            
            if not alarm_state:
                # 首次离岗告警
                redis_client.set(alarm_state_key, "alarmed", ex=self.CACHE_EXPIRE_STATIC)
                self.last_alarm_time[person_id] = datetime.now()
                
                content = {
                    "person_id": person_id,
                    "person_name": person["name"],
                    "post": person["post"],
                    "duty_period": person["duty_period"],
                    "allowed_max_min": max_absent_min,
                    "current_absent_sec": int(absent_seconds),
                    "source_type": self.source_type,
                    "source_id": self.source_id
                }
                return True, "离岗首次告警", content
            
            # 检查是否需要持续告警（每5分钟一次）
            limit_key = self.CACHE_KEY_ALARM_LIMIT.format(person_id=person_id)
            if not redis_client.exists(limit_key):
                # 设置限流
                redis_client.set(limit_key, "1", ex=self.CACHE_EXPIRE_ALARM_LIMIT)
                
                # 计算距首次告警的间隔
                if person_id in self.last_alarm_time:
                    elapsed = (datetime.now() - self.last_alarm_time[person_id]).total_seconds() / 60
                    interval_str = f"距首次告警{int(elapsed)}分钟"
                else:
                    interval_str = "持续离岗"
                
                content = {
                    "person_id": person_id,
                    "person_name": person["name"],
                    "post": person["post"],
                    "duty_period": person["duty_period"],
                    "allowed_max_min": max_absent_min,
                    "current_absent_sec": int(absent_seconds),
                    "alarm_interval": interval_str,
                    "source_type": self.source_type,
                    "source_id": self.source_id
                }
                return True, "离岗持续告警", content
        
        return False, "", {}
    
    def check_return_alarm(self, person_id: str) -> tuple[bool, Dict]:
        """检查是否应该触发回岗告警"""
        person = self.persons.get(person_id)
        if not person:
            return False, {}
        
        # 检查之前是否处于离岗状态
        alarm_state_key = self.CACHE_KEY_ALARM_STATE.format(person_id=person_id)
        alarm_state = redis_client.get(alarm_state_key)
        
        if alarm_state:
            # 之前有离岗告警，现在回岗了
            absent_start = self.absent_start_time.get(person_id)
            return_time = datetime.now()
            
            if absent_start:
                total_absent_seconds = (return_time - absent_start).total_seconds()
            else:
                total_absent_seconds = 0
            
            content = {
                "person_id": person_id,
                "person_name": person["name"],
                "post": person["post"],
                "duty_period": person["duty_period"],
                "allowed_max_min": person["max_absent_min"],
                "absent_start": absent_start.isoformat() if absent_start else None,
                "return_time": return_time.isoformat(),
                "total_absent_seconds": int(total_absent_seconds),
                "source_type": self.source_type,
                "source_id": self.source_id
            }
            
            # 清理状态
            self.reset_absent_timer(person_id)
            redis_client.delete(alarm_state_key)
            self.person_status[person_id] = AbsentStatus.RETURNED
            
            return True, content
        
        return False, {}
    
    def process_frame(self, frame) -> List[Dict]:
        """处理视频帧，检测人员在岗状态（带防抖）"""
        alarms = []
        
        if not self.is_running:
            return alarms
        
        # 检测并匹配人脸
        matched_faces = face_recognizer.match_faces_in_frame(frame)
        matched_person_ids = {person_id for person_id, _ in matched_faces}
        
        # 处理每个人员
        for person_id, person in self.persons.items():
            # 检查是否在站岗时间
            if not self.is_in_duty_period(person["duty_period"]):
                continue
            
            # 初始化防抖计数器
            if person_id not in self.missed_frame_count:
                self.missed_frame_count[person_id] = 0
            if person_id not in self.matched_frame_count:
                self.matched_frame_count[person_id] = 0
            
            current_status = self.person_status.get(person_id, AbsentStatus.ON_DUTY)
            
            if person_id in matched_person_ids:
                # 识别到人员
                self.matched_frame_count[person_id] += 1
                self.missed_frame_count[person_id] = 0
                
                # 防抖：连续多帧检测到才确认在岗
                if current_status == AbsentStatus.ABSENT and self.matched_frame_count[person_id] >= self.PRESENT_CONFIRM_FRAMES:
                    # 从离岗状态恢复
                    should_alarm, content = self.check_return_alarm(person_id)
                    if should_alarm:
                        alarms.append({
                            "type": "离岗告警解除",
                            "content": content
                        })
                    self.person_status[person_id] = AbsentStatus.ON_DUTY
                    print(f"[DEBUG] {person_id} confirmed PRESENT after {self.matched_frame_count[person_id]} frames")
                elif current_status == AbsentStatus.ON_DUTY:
                    # 已经在岗，重置计时器
                    self.reset_absent_timer(person_id)
            else:
                # 未识别到人员
                self.missed_frame_count[person_id] += 1
                self.matched_frame_count[person_id] = 0
                
                # 防抖：连续多帧未检测到才确认离岗
                if self.missed_frame_count[person_id] >= self.ABSENT_CONFIRM_FRAMES:
                    # 更新离岗计时
                    absent_sec = self.update_absent_timer(person_id)
                    
                    # 检查是否应该告警
                    should_alarm, alarm_type, content = self.check_should_alarm(person_id)
                    if should_alarm:
                        self.person_status[person_id] = AbsentStatus.ABSENT
                        alarms.append({
                            "type": alarm_type,
                            "content": content
                        })
                        print(f"[DEBUG] {person_id} confirmed ABSENT after {self.missed_frame_count[person_id]} frames, alarm: {alarm_type}")
        
        return alarms
    
    def start_detection(self, source_id: str, source_type: str = "camera"):
        """启动离岗检测"""
        self.is_running = True
        self.source_id = source_id
        self.source_type = source_type
        
        # 清除旧的计时器和告警状态
        for person_id in self.persons.keys():
            timer_key = self.CACHE_KEY_TIMER.format(person_id=person_id)
            start_key = f"abrs:absent:timer_start:{person_id}"
            alarm_state_key = self.CACHE_KEY_ALARM_STATE.format(person_id=person_id)
            redis_client.delete(timer_key)
            redis_client.delete(start_key)
            redis_client.delete(alarm_state_key)
        
        # 清除防抖计数器
        self.missed_frame_count.clear()
        self.matched_frame_count.clear()
        
        print(f"离岗检测已启动 - 源: {source_id}, 类型: {source_type}")
    
    def stop_detection(self):
        """停止离岗检测"""
        self.is_running = False
        self.source_id = None
        self.source_type = None
        print("离岗检测已停止")
    
    def get_status(self, person_id: Optional[str] = None) -> Dict:
        """获取检测状态"""
        if person_id:
            return {
                "person_id": person_id,
                "status": self.person_status.get(person_id, AbsentStatus.ON_DUTY).value,
                "absent_duration": self.get_absent_duration(person_id),
                "is_running": self.is_running
            }
        else:
            return {
                "persons": [
                    {
                        "person_id": pid,
                        "status": status.value,
                        "absent_duration": self.get_absent_duration(pid)
                    }
                    for pid, status in self.person_status.items()
                ],
                "is_running": self.is_running,
                "source_id": self.source_id,
                "source_type": self.source_type
            }


# 全局检测器实例
absent_detector = AbsentDetector()
