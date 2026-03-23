from typing import Optional, Dict, Any
from datetime import datetime, time
from utils.redis_utils import redis_client


class AbsentDetector:
    CACHE_KEY_PERSON_CONFIG = "abrs:absent:person:config"
    CACHE_KEY_TIMER = "abrs:absent:timer:{person_id}"
    CACHE_KEY_ALARM_LIMIT = "abrs:absent:alarm:limit:{person_id}"

    CACHE_EXPIRE_STATIC = 300
    CACHE_EXPIRE_DYNAMIC = 10

    def __init__(self):
        self.persons: Dict[str, Any] = {}
        self.absent_timers: Dict[str, float] = {}
        self.alarm_sent: Dict[str, datetime] = {}

    def load_person_config(self, persons_data: list):
        for person in persons_data:
            self.persons[person["person_id"]] = person
        redis_client.set(self.CACHE_KEY_PERSON_CONFIG, persons_data, ex=self.CACHE_EXPIRE_STATIC)

    def is_in_duty_period(self, duty_period: str) -> bool:
        try:
            start_str, end_str = duty_period.split("-")
            now = datetime.now().time()
            start = time(int(start_str[:2]), int(start_str[3:]))
            end = time(int(end_str[:2]), int(end_str[3:]))
            return start <= now <= end
        except Exception:
            return False

    def update_absent_timer(self, person_id: str):
        key = self.CACHE_KEY_TIMER.format(person_id=person_id)
        current = self.absent_timers.get(person_id, 0)
        self.absent_timers[person_id] = current + 1
        redis_client.set(key, self.absent_timers[person_id], ex=self.CACHE_EXPIRE_DYNAMIC)

    def reset_absent_timer(self, person_id: str):
        key = self.CACHE_KEY_TIMER.format(person_id=person_id)
        self.absent_timers.pop(person_id, None)
        redis_client.delete(key)

    def should_send_alarm(self, person_id: str, max_absent_min: int) -> tuple[bool, str]:
        person = self.persons.get(person_id)
        if not person:
            return False, ""

        absent_seconds = self.absent_timers.get(person_id, 0)
        absent_min = absent_seconds / 60

        if absent_min >= max_absent_min:
            limit_key = self.CACHE_KEY_ALARM_LIMIT.format(person_id=person_id)
            if redis_client.exists(limit_key):
                return False, ""
            redis_client.set(limit_key, "1", ex=300)
            return True, "离岗首次告警"

        return False, ""

    def should_send_continue_alarm(self, person_id: str) -> bool:
        if person_id in self.alarm_sent:
            last_alarm = self.alarm_sent[person_id]
            elapsed = (datetime.now() - last_alarm).total_seconds() / 60
            return elapsed >= 5
        return False

    def record_alarm_sent(self, person_id: str):
        self.alarm_sent[person_id] = datetime.now()


absent_detector = AbsentDetector()
