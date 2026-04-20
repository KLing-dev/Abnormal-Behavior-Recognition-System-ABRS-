"""
面部识别模块 - 用于离岗检测
支持面部特征提取和匹配
"""
import cv2
import numpy as np
import base64
from typing import Optional, List, Tuple
from datetime import datetime


class FaceRecognizer:
    """面部识别器"""
    
    def __init__(self):
        # 使用OpenCV的DNN人脸检测器
        self.face_detector = cv2.dnn.readNetFromCaffe(
            "models/deploy.prototxt",
            "models/res10_300x300_ssd_iter_140000.caffemodel"
        ) if self._check_model_files() else None
        
        # 使用简单的特征匹配（不依赖cv2.face模块）
        self.known_faces = {}  # person_id -> face_feature
        
    def _check_model_files(self) -> bool:
        """检查模型文件是否存在"""
        import os
        prototxt = "models/deploy.prototxt"
        model = "models/res10_300x300_ssd_iter_140000.caffemodel"
        return os.path.exists(prototxt) and os.path.exists(model)
    
    def extract_face_feature(self, face_img: np.ndarray) -> Optional[np.ndarray]:
        """提取面部特征 - 使用多维度特征"""
        try:
            # 转换为灰度图
            if len(face_img.shape) == 3:
                gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
            else:
                gray = face_img
            
            # 调整大小为标准化尺寸
            gray = cv2.resize(gray, (100, 100))
            
            # 直方图均衡化增强对比度
            gray = cv2.equalizeHist(gray)
            
            # 提取多种特征
            features = []
            
            # 1. 原始像素特征（降采样）
            small = cv2.resize(gray, (20, 20))
            features.extend(small.flatten() / 255.0)
            
            # 2. 直方图特征
            hist = cv2.calcHist([gray], [0], None, [16], [0, 256])
            hist = hist.flatten() / (gray.shape[0] * gray.shape[1])
            features.extend(hist)
            
            # 3. LBP特征（局部二值模式）
            lbp = self._compute_lbp(gray)
            lbp_hist = cv2.calcHist([lbp], [0], None, [16], [0, 256])
            lbp_hist = lbp_hist.flatten() / (lbp.shape[0] * lbp.shape[1])
            features.extend(lbp_hist)
            
            return np.array(features, dtype=np.float32)
        except Exception as e:
            print(f"提取面部特征失败: {e}")
            return None
    
    def _compute_lbp(self, gray: np.ndarray) -> np.ndarray:
        """计算LBP特征"""
        height, width = gray.shape
        lbp = np.zeros((height-2, width-2), dtype=np.uint8)
        
        for i in range(1, height-1):
            for j in range(1, width-1):
                center = gray[i, j]
                code = 0
                code |= (gray[i-1, j-1] > center) << 7
                code |= (gray[i-1, j] > center) << 6
                code |= (gray[i-1, j+1] > center) << 5
                code |= (gray[i, j+1] > center) << 4
                code |= (gray[i+1, j+1] > center) << 3
                code |= (gray[i+1, j] > center) << 2
                code |= (gray[i+1, j-1] > center) << 1
                code |= (gray[i, j-1] > center) << 0
                lbp[i-1, j-1] = code
        
        return lbp
    
    def detect_faces(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """检测图像中的所有人脸，使用严格的过滤条件减少误检"""
        faces = []
        
        if self.face_detector is None:
            # 降级方案：使用Haar级联分类器
            return self._detect_faces_haar(frame)
        
        try:
            h, w = frame.shape[:2]
            blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)), 1.0,
                                         (300, 300), (104.0, 177.0, 123.0))
            self.face_detector.setInput(blob)
            detections = self.face_detector.forward()
            
            # 计算图片对角线长度作为参考
            img_diagonal = np.sqrt(h**2 + w**2)
            min_face_size = int(img_diagonal * 0.15)  # 提高最小人脸为图片对角线的15%
            max_face_size = int(img_diagonal * 0.8)   # 最大人脸为图片对角线的80%
            
            for i in range(detections.shape[2]):
                confidence = detections[0, 0, i, 2]
                # 大幅提高置信度阈值到0.85，严格减少误检
                if confidence > 0.85:
                    box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                    (startX, startY, endX, endY) = box.astype("int")
                    
                    face_w = endX - startX
                    face_h = endY - startY
                    
                    # 过滤掉太小或太大的人脸（可能是误检）
                    if face_w < min_face_size or face_h < min_face_size:
                        continue
                    if face_w > max_face_size or face_h > max_face_size:
                        continue
                    
                    # 过滤掉宽高比异常的人脸（正常人脸比例在0.6-1.4之间）
                    aspect_ratio = face_w / face_h if face_h > 0 else 0
                    if aspect_ratio < 0.6 or aspect_ratio > 1.4:
                        continue
                    
                    faces.append((startX, startY, face_w, face_h))
                    
        except Exception as e:
            print(f"DNN人脸检测失败，使用Haar降级: {e}")
            return self._detect_faces_haar(frame)
        
        return faces
    
    def _detect_faces_haar(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """使用Haar级联分类器检测人脸（降级方案）"""
        try:
            face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
            )
            return list(faces)
        except Exception as e:
            print(f"Haar人脸检测失败: {e}")
            return []
    
    def register_person(self, person_id: str, face_img: np.ndarray) -> Optional[str]:
        """注册人员面部信息"""
        feature = self.extract_face_feature(face_img)
        if feature is None:
            return None
        
        # 将特征编码为Base64
        feature_bytes = feature.tobytes()
        feature_b64 = base64.b64encode(feature_bytes).decode('utf-8')
        
        self.known_faces[person_id] = feature
        return feature_b64
    
    def load_person_feature(self, person_id: str, feature_b64: str) -> bool:
        """从Base64加载人员面部特征"""
        try:
            feature_bytes = base64.b64decode(feature_b64)
            # 计算特征维度
            feature = np.frombuffer(feature_bytes, dtype=np.float32)
            
            if feature is not None and len(feature) > 0:
                self.known_faces[person_id] = feature
                return True
        except Exception as e:
            print(f"加载人员特征失败 {person_id}: {e}")
        
        return False
    
    def match_face(self, face_img: np.ndarray, 
                   threshold: float = 0.3) -> Optional[str]:
        """匹配面部，返回最匹配的人员ID"""
        if not self.known_faces:
            return None
        
        feature = self.extract_face_feature(face_img)
        if feature is None:
            return None
        
        best_match = None
        best_similarity = -1.0
        
        for person_id, known_feature in self.known_faces.items():
            # 使用余弦相似度
            similarity = self._cosine_similarity(feature, known_feature)
            
            if similarity > best_similarity and similarity > threshold:
                best_similarity = similarity
                best_match = person_id
        
        return best_match
    
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """计算余弦相似度"""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return np.dot(a, b) / (norm_a * norm_b)
    
    def match_faces_in_frame(self, frame: np.ndarray,
                             threshold: float = 0.3) -> List[Tuple[str, Tuple[int, int, int, int]]]:
        """在视频帧中检测并匹配所有人脸"""
        results = []
        faces = self.detect_faces(frame)
        
        for (x, y, w, h) in faces:
            # 提取人脸区域
            face_roi = frame[y:y+h, x:x+w]
            if face_roi.size == 0:
                continue
            
            # 匹配人脸
            person_id = self.match_face(face_roi, threshold)
            if person_id:
                results.append((person_id, (x, y, w, h)))
        
        return results


# 全局面部识别器实例
face_recognizer = FaceRecognizer()
