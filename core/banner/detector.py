from typing import Optional, Dict, Any, List, Set
from datetime import datetime
from loguru import logger
import re


class BannerDetector:
    CACHE_KEY_AREA_CONFIG = "abrs:banner:area:config"
    CACHE_KEY_ALERT = "abrs:banner:alert:{track_id}"
    CACHE_KEY_COUNT = "abrs:banner:count"

    CACHE_EXPIRE_STATIC = 300
    CACHE_EXPIRE_DYNAMIC = 10

    ALERT_COOLDOWN_SEC = 2

    def __init__(self):
        self.areas: Dict[str, Any] = {}
        self.illegal_words: List[str] = []
        self.last_alert: Dict[str, Dict[str, Any]] = {}
        self.alert_count: int = 0
        self.frame_alerted_texts: Set[str] = set()

    def load_illegal_words(self, words: List[str]):
        self.illegal_words = [w.lower().strip() for w in words if w.strip()]
        logger.info(f"Loaded {len(self.illegal_words)} illegal words")

    def load_area_config(self, areas_data: list):
        for area in areas_data:
            self.areas[area["area_id"]] = area
        logger.info(f"Loaded {len(self.areas)} area configs")

    def get_area_coords(self, area_id: str) -> Optional[tuple]:
        area = self.areas.get(area_id)
        if not area:
            return None
        try:
            coords = area["coords"].split(",")
            return (int(coords[0]), int(coords[1]), int(coords[2]), int(coords[3]))
        except Exception:
            return None

    def check_illegal(self, text: str) -> tuple[bool, Optional[str]]:
        text_lower = text.lower()
        for illegal_word in self.illegal_words:
            if illegal_word in text_lower:
                return True, illegal_word
        return False, None

    def should_alert(self, track_id: str, text: str, current_time: datetime) -> bool:
        text_key = f"{track_id}:{text}"

        if text_key in self.frame_alerted_texts:
            return False

        if track_id in self.last_alert:
            last_info = self.last_alert[track_id]
            if last_info['text'] == text:
                time_diff = (current_time - last_info['time']).total_seconds()
                if time_diff < self.ALERT_COOLDOWN_SEC:
                    return False

        return True

    def record_alert(self, track_id: str, text: str, illegal_word: str, current_time: datetime):
        text_key = f"{track_id}:{text}"
        self.last_alert[track_id] = {'text': text, 'time': current_time}
        self.frame_alerted_texts.add(text_key)
        self.alert_count += 1

    def clear_frame_state(self):
        self.frame_alerted_texts.clear()

    def get_alert_count(self) -> int:
        return self.alert_count

    def reset_alert_count(self):
        self.alert_count = 0


banner_detector = BannerDetector()