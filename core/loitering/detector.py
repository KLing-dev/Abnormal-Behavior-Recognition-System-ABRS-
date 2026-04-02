from typing import Optional, Dict, Any
from datetime import datetime
from utils.redis_utils import redis_client


class LoiteringDetector:
    CACHE_KEY_AREA_CONFIG = "abrs:loitering:area:config"
    CACHE_KEY_DURATION = "abrs:loitering:duration:{area_id}:{track_id}"
    CACHE_KEY_COUNT = "abrs:loitering:count:{area_id}"

    CACHE_EXPIRE_STATIC = 300
    CACHE_EXPIRE_DYNAMIC = 10

    def __init__(self):
        self.areas: Dict[str, Any] = {}
        self.track_durations: Dict[str, float] = {}
        self.loitering_count: Dict[str, int] = {}

    def load_area_config(self, areas_data: list):
        for area in areas_data:
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

    def is_person_in_area(self, x: int, y: int, area_id: str) -> bool:
        coords = self.get_area_coords(area_id)
        if not coords:
            return False
        x1, y1, x2, y2 = coords
        return x1 <= x <= x2 and y1 <= y <= y2

    def update_duration(self, area_id: str, track_id: str):
        key = self.CACHE_KEY_DURATION.format(area_id=area_id, track_id=track_id)
        current = self.track_durations.get(f"{area_id}:{track_id}", 0)
        self.track_durations[f"{area_id}:{track_id}"] = current + 1
        redis_client.set(key, self.track_durations[f"{area_id}:{track_id}"], ex=self.CACHE_EXPIRE_DYNAMIC)

    def remove_track(self, area_id: str, track_id: str):
        key = self.CACHE_KEY_DURATION.format(area_id=area_id, track_id=track_id)
        self.track_durations.pop(f"{area_id}:{track_id}", None)
        redis_client.delete(key)

    def check_loitering(self, area_id: str) -> list:
        area = self.areas.get(area_id)
        if not area:
            return []

        threshold_min = area.get("threshold_min", 10)
        loitering_tracks = []

        for key, duration in self.track_durations.items():
            if key.startswith(f"{area_id}:"):
                duration_min = duration / 60
                if duration_min >= threshold_min:
                    track_id = key.split(":")[2]
                    loitering_tracks.append(track_id)

        count_key = self.CACHE_KEY_COUNT.format(area_id=area_id)
        self.loitering_count[area_id] = len(loitering_tracks)
        redis_client.set(count_key, len(loitering_tracks), ex=self.CACHE_EXPIRE_DYNAMIC)

        return loitering_tracks

    def get_loitering_count(self, area_id: str) -> int:
        return self.loitering_count.get(area_id, 0)

    def clear_area_state(self, area_id: str):
        for key in list(self.track_durations.keys()):
            if key.startswith(f"{area_id}:"):
                track_id = key.split(":")[2]
                self.remove_track(area_id, track_id)
        count_key = self.CACHE_KEY_COUNT.format(area_id=area_id)
        self.loitering_count.pop(area_id, None)
        redis_client.delete(count_key)


loitering_detector = LoiteringDetector()
