from typing import Optional, Dict, Any, List
from datetime import datetime
from utils.redis_utils import redis_client


class LoiteringDetector:
    CACHE_KEY_AREA_CONFIG = "abrs:loitering:area:config"
    CACHE_KEY_DURATION = "abrs:loitering:duration:{area_id}:{track_id}"
    CACHE_KEY_COUNT = "abrs:loitering:count:{area_id}"

    CACHE_EXPIRE_STATIC = 300
    CACHE_EXPIRE_DYNAMIC = 10

    DEFAULT_THRESHOLD_MIN = 10
    MIN_LOITERING_MIN = 1

    def __init__(self):
        self.areas: Dict[str, Any] = {}
        self.track_durations: Dict[str, float] = {}
        self.loitering_count: Dict[str, int] = {}
        self.track_last_seen: Dict[str, datetime] = {}

    def load_area_config(self, areas_data: list):
        for area in areas_data:
            if "threshold_min" not in area or not area["threshold_min"]:
                area["threshold_min"] = self.DEFAULT_THRESHOLD_MIN
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

    def get_threshold(self, area_id: str) -> int:
        area = self.areas.get(area_id)
        if area and "threshold_min" in area:
            return area["threshold_min"]
        return self.DEFAULT_THRESHOLD_MIN

    def is_person_in_area(self, x: int, y: int, area_id: str) -> bool:
        coords = self.get_area_coords(area_id)
        if not coords:
            return False
        x1, y1, x2, y2 = coords
        return x1 <= x <= x2 and y1 <= y <= y2

    def update_duration(self, area_id: str, track_id: str, duration_frames: int = 1):
        key = self.CACHE_KEY_DURATION.format(area_id=area_id, track_id=track_id)
        current = self.track_durations.get(f"{area_id}:{track_id}", 0)
        self.track_durations[f"{area_id}:{track_id}"] = current + duration_frames
        self.track_last_seen[f"{area_id}:{track_id}"] = datetime.now()
        redis_client.set(key, self.track_durations[f"{area_id}:{track_id}"], ex=self.CACHE_EXPIRE_DYNAMIC)

    def remove_track(self, area_id: str, track_id: str):
        key = self.CACHE_KEY_DURATION.format(area_id=area_id, track_id=track_id)
        self.track_durations.pop(f"{area_id}:{track_id}", None)
        self.track_last_seen.pop(f"{area_id}:{track_id}", None)
        redis_client.delete(key)

    def mark_person_left(self, area_id: str, track_id: str):
        self.track_last_seen[f"{area_id}:{track_id}_left"] = datetime.now()

    def get_loitering_duration_min(self, area_id: str, track_id: str) -> float:
        duration_frames = self.track_durations.get(f"{area_id}:{track_id}", 0)
        return duration_frames / 60.0

    def check_loitering(self, area_id: str) -> List[str]:
        area = self.areas.get(area_id)
        if not area:
            return []

        threshold_min = self.get_threshold(area_id)
        loitering_tracks = []

        for key, duration in list(self.track_durations.items()):
            if key.startswith(f"{area_id}:"):
                parts = key.rsplit(":", 2)
                if len(parts) >= 3:
                    track_id = parts[2]
                else:
                    track_id = parts[-1]
                duration_min = duration / 60.0

                if duration_min >= threshold_min:
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
                parts = key.rsplit(":", 2)
                if len(parts) >= 3:
                    track_id = parts[2]
                else:
                    track_id = parts[-1]
                self.remove_track(area_id, track_id)
        count_key = self.CACHE_KEY_COUNT.format(area_id=area_id)
        self.loitering_count.pop(area_id, None)
        redis_client.delete(count_key)

    def get_person_status(self, area_id: str, track_id: str) -> Dict[str, Any]:
        duration_min = self.get_loitering_duration_min(area_id, track_id)
        threshold_min = self.get_threshold(area_id)
        is_loitering = duration_min >= threshold_min
        is_brief = duration_min < self.MIN_LOITERING_MIN

        return {
            "track_id": track_id,
            "duration_min": round(duration_min, 2),
            "threshold_min": threshold_min,
            "is_loitering": is_loitering,
            "is_brief": is_brief,
            "status": "徘徊" if is_loitering else ("短暂路过" if is_brief else "停留中")
        }


loitering_detector = LoiteringDetector()
