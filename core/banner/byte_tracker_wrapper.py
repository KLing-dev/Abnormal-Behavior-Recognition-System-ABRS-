"""
ByteTrack 追踪器包装类
用于将 YOLO 检测结果转换为 ByteTrack 追踪
"""

import numpy as np
from pathlib import Path
import sys

# 添加 ultralytics 路径
yolov12_path = Path(__file__).parent.parent / 'yolov12'
if str(yolov12_path) not in sys.path:
    sys.path.insert(0, str(yolov12_path))

from ultralytics.trackers.byte_tracker import BYTETracker as UltralyticsBYTETracker


class TrackedObject:
    """追踪结果封装类"""
    def __init__(self, tlbr, score, track_id):
        self.tlbr = tlbr
        self.score = score
        self.track_id = track_id


class SimpleByteTracker:
    """简化的 ByteTrack 追踪器封装"""
    
    def __init__(self, track_thresh=0.3, track_buffer=30, match_thresh=0.8, frame_rate=30):
        """
        初始化 ByteTrack 追踪器
        
        参数：
            track_thresh: 检测置信度阈值
            track_buffer: 追踪缓冲区大小
            match_thresh: 匹配阈值
            frame_rate: 视频帧率
        """
        # 创建模拟的 args 对象
        class Args:
            def __init__(self):
                self.track_thresh = track_thresh
                self.track_buffer = track_buffer
                self.match_thresh = match_thresh
                self.track_low_thresh = 0.2
                self.track_high_thresh = track_thresh
                self.new_track_thresh = 0.25
                self.match_thresh = match_thresh
                self.fuse_score = True
        
        self.args = Args()
        self.frame_id = 0
        
        # 初始化原始 BYTETracker
        self.tracker = UltralyticsBYTETracker(self.args, frame_rate)
    
    def update(self, detections, frame=None):
        """
        更新追踪器
        
        参数：
            detections: 检测结果列表，每个元素为 [x1, y1, x2, y2, conf]
            frame: 当前帧图像（可选）
        
        返回：
            online_targets: 追踪结果列表（TrackedObject 对象）
        """
        self.frame_id += 1
        
        if len(detections) == 0:
            return []
        
        # 转换为 BYTETracker 需要的格式
        detections = np.array(detections)
        
        # 提取边界框和置信度
        if detections.shape[1] == 5:
            bboxes = detections[:, :4]  # xyxy 格式
            scores = detections[:, 4]
        else:
            return []
        
        # 转换为 xywh 格式（BYTETracker 需要）
        bboxes_xywh = np.zeros_like(bboxes)
        bboxes_xywh[:, 0] = (bboxes[:, 0] + bboxes[:, 2]) / 2  # x center
        bboxes_xywh[:, 1] = (bboxes[:, 1] + bboxes[:, 3]) / 2  # y center
        bboxes_xywh[:, 2] = bboxes[:, 2] - bboxes[:, 0]  # width
        bboxes_xywh[:, 3] = bboxes[:, 3] - bboxes[:, 1]  # height
        
        # 创建模拟的 results 对象
        class FakeResults:
            def __init__(self, xywh, conf, cls):
                self.xywh = xywh
                self.xywhr = xywh  # for compatibility
                self.conf = conf
                self.cls = cls
        
        # 假设所有检测都是同一类别（0 = banner）
        cls = np.zeros(len(scores))
        
        fake_results = FakeResults(bboxes_xywh, scores, cls)
        
        # 调用 BYTETracker 的 update 方法
        tracked_results = self.tracker.update(fake_results, frame)
        
        # 转换为 TrackedObject 对象列表
        # tracked_results 是一个 numpy 数组，每行包含 [x1, y1, x2, y2, track_id, score, cls, idx]
        result = []
        if len(tracked_results) > 0:
            for track_data in tracked_results:
                # track_data 格式: [x1, y1, x2, y2, track_id, score, cls, idx]
                x1, y1, x2, y2 = track_data[:4]
                track_id = int(track_data[4])
                score = float(track_data[5])
                tlbr = np.array([x1, y1, x2, y2])
                result.append(TrackedObject(
                    tlbr=tlbr,
                    score=score,
                    track_id=track_id
                ))
        
        return result
