from typing import Optional, Dict, Any
from datetime import datetime
from utils.redis_utils import redis_client


class GatheringDetector:
    CACHE_KEY_AREA_CONFIG = "abrs:gathering:area:config"
    CACHE_KEY_COUNT = "abrs:gathering:count:{area_id}"
    CACHE_KEY_LEVEL = "abrs:gathering:level:{area_id}"
    CACHE_KEY_DURATION = "abrs:gathering:duration:{area_id}"

    CACHE_EXPIRE_STATIC = 300
    CACHE_EXPIRE_DYNAMIC = 10

    DEFAULT_THRESHOLDS = {
        "light": 5,
        "medium": 10,
        "urgent": 20
    }

    def __init__(self):
        self.areas: Dict[str, Any] = {}
        self.person_counts: Dict[str, int] = {}
        self.current_levels: Dict[str, str] = {}
        self.durations: Dict[str, float] = {}

    def load_area_config(self, areas_data: list):
        for area in areas_data:
            if "level_thresholds" not in area or not area["level_thresholds"]:
                area["level_thresholds"] = self.DEFAULT_THRESHOLDS
            self.areas[area["area_id"]] = area
        redis_client.set(self.CACHE_KEY_AREA_CONFIG, areas_data, ex=self.CACHE_EXPIRE_STATIC)

    def get_area_coords(self, area_id: str) -> Optional[tuple]:
        area = self.areas.get(area_id)
        if not area:
            return None
        try:
            coords = area["coords"].split(",")
            return (int(coords[0]), int(coords[1]), int(coords[2]), int(coords[3]))
        except Exception:
            return None

    def get_level_thresholds(self, area_id: str) -> Dict[str, int]:
        area = self.areas.get(area_id)
        if area and "level_thresholds" in area:
            return area["level_thresholds"]
        return self.DEFAULT_THRESHOLDS

    def is_person_in_area(self, x: int, y: int, area_id: str) -> bool:
        coords = self.get_area_coords(area_id)
        if not coords:
            return False
        x1, y1, x2, y2 = coords
        return x1 <= x <= x2 and y1 <= y <= y2

    def update_person_count(self, area_id: str, count: int):
        key = self.CACHE_KEY_COUNT.format(area_id=area_id)
        self.person_counts[area_id] = count
        redis_client.set(key, count, ex=self.CACHE_EXPIRE_DYNAMIC)

    def determine_level(self, area_id: str, count: int) -> Optional[str]:
        thresholds = self.get_level_thresholds(area_id)
        if count >= thresholds.get("urgent", 20):
            return "紧急"
        elif count >= thresholds.get("medium", 10):
            return "中度"
        elif count >= thresholds.get("light", 5):
            return "轻度"
        return None

    def update_level(self, area_id: str, level: Optional[str]):
        key = self.CACHE_KEY_LEVEL.format(area_id=area_id)
        if level:
            self.current_levels[area_id] = level
            redis_client.set(key, level, ex=self.CACHE_EXPIRE_DYNAMIC)
        else:
            self.current_levels.pop(area_id, None)
            redis_client.delete(key)

    def update_duration(self, area_id: str):
        key = self.CACHE_KEY_DURATION.format(area_id=area_id)
        current = self.durations.get(area_id, 0)
        self.durations[area_id] = current + 1
        redis_client.set(key, self.durations[area_id], ex=self.CACHE_EXPIRE_DYNAMIC)

    def check_gathering(self, area_id: str) -> tuple[Optional[str], int]:
        count = self.person_counts.get(area_id, 0)
        level = self.determine_level(area_id, count)

        if level:
            self.update_level(area_id, level)
            self.update_duration(area_id)
            duration = self.durations.get(area_id, 0)
            return level, duration / 60
        else:
            self.update_level(area_id, None)
            duration = self.durations.pop(area_id, 0)
            return None, 0

    def should_send_alarm(self, area_id: str, level: str) -> bool:
        current_level = self.current_levels.get(area_id)
        return current_level == level

    def get_current_level(self, area_id: str) -> Optional[str]:
        return self.current_levels.get(area_id)

    def clear_area_state(self, area_id: str):
        count_key = self.CACHE_KEY_COUNT.format(area_id=area_id)
        level_key = self.CACHE_KEY_LEVEL.format(area_id=area_id)
        duration_key = self.CACHE_KEY_DURATION.format(area_id=area_id)

        self.person_counts.pop(area_id, None)
        self.current_levels.pop(area_id, None)
        self.durations.pop(area_id, None)

        redis_client.delete(count_key)
        redis_client.delete(level_key)
        redis_client.delete(duration_key)


gathering_detector = GatheringDetector()
