"""
离岗识别模块
"""
from core.absent.detector import AbsentDetector, AbsentStatus, absent_detector
from core.absent.face_recognition import FaceRecognizer, face_recognizer
from core.absent.video_stream import VideoStreamProcessor, AbsentStreamManager, stream_manager

__all__ = [
    "AbsentDetector",
    "AbsentStatus", 
    "absent_detector",
    "FaceRecognizer",
    "face_recognizer",
    "VideoStreamProcessor",
    "AbsentStreamManager",
    "stream_manager"
]
