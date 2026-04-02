import cv2
import numpy as np
from typing import Optional, Tuple


def read_video_capture(source_type: str, source: str = "", device_id: int = 0) -> Optional[cv2.VideoCapture]:
    cap = None
    if source_type == "camera":
        cap = cv2.VideoCapture(device_id)
    elif source_type == "file":
        cap = cv2.VideoCapture(source)
    elif source_type == "stream":
        cap = cv2.VideoCapture(source)

    if cap and not cap.isOpened():
        return None
    return cap


def read_frame(cap: cv2.VideoCapture) -> Optional[np.ndarray]:
    if not cap or not cap.isOpened():
        return None
    ret, frame = cap.read()
    if not ret:
        return None
    return frame


def parse_coords(coords_str: str) -> Tuple[int, int, int, int]:
    parts = coords_str.split(',')
    return int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])


def is_point_in_area(x: int, y: int, x1: int, y1: int, x2: int, y2: int) -> bool:
    return x1 <= x <= x2 and y1 <= y <= y2


def draw_rectangle(frame: np.ndarray, x1: int, y1: int, x2: int, y2: int, color: Tuple[int, int, int] = (0, 255, 0), thickness: int = 2):
    return cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)


def put_text(frame: np.ndarray, text: str, x: int, y: int, color: Tuple[int, int, int] = (255, 255, 255), font_scale: float = 1.0, thickness: int = 2):
    return cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness)
