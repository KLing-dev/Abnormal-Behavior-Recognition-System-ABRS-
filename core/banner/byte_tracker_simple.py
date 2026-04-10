"""
简化版 BYTETracker - 不依赖 ultralytics
"""
import numpy as np
from collections import deque
from typing import List, Tuple, Optional
import math


class KalmanFilterXYAH:
    """简单的卡尔曼滤波器"""

    def __init__(self):
        self._motion_mat = np.eye(8, 8)
        self._motion_mat[0, 4] = 1
        self._motion_mat[1, 5] = 1
        self._motion_mat[2, 6] = 1
        self._motion_mat[3, 7] = 1

        self._update_mat = np.eye(4, 8)

        self._std_weight_position = 1.0 / 20
        self._std_weight_velocity = 1.0 / 160

    def initiate(self, measurement: np.ndarray):
        mean_pos = measurement
        mean_vel = np.zeros_like(mean_pos)
        mean = np.r_[mean_pos, mean_vel]

        std = [
            2 * self._std_weight_position * measurement[2],
            2 * self._std_weight_position * measurement[3],
            2 * self._std_weight_position * measurement[2],
            2 * self._std_weight_position * measurement[3],
            10 * self._std_weight_velocity * measurement[2],
            10 * self._std_weight_velocity * measurement[3],
            10 * self._std_weight_velocity * measurement[2],
            10 * self._std_weight_velocity * measurement[3],
        ]
        covariance = np.diag(np.square(std))
        return mean, covariance

    def predict(self, mean: np.ndarray, covariance: np.ndarray):
        std_pos = [
            self._std_weight_position * mean[2],
            self._std_weight_position * mean[3],
            self._std_weight_position * mean[2],
            self._std_weight_position * mean[3],
        ]
        std_vel = [
            self._std_weight_velocity * mean[2],
            self._std_weight_velocity * mean[3],
            self._std_weight_velocity * mean[2],
            self._std_weight_velocity * mean[3],
        ]
        motion_cov = np.diag(np.square(np.r_[std_pos, std_vel]))

        mean = self._motion_mat @ mean
        covariance = self._motion_mat @ covariance @ self._motion_mat.T + motion_cov

        return mean, covariance

    def project(self, mean: np.ndarray, covariance: np.ndarray):
        std = [
            self._std_weight_position * mean[2],
            self._std_weight_position * mean[3],
            self._std_weight_position * mean[2],
            self._std_weight_position * mean[3],
        ]
        innovation_cov = np.diag(np.square(std))

        mean = self._update_mat @ mean
        covariance = self._update_mat @ covariance @ self._update_mat.T + innovation_cov

        return mean, covariance

    def update(self, mean: np.ndarray, covariance: np.ndarray, measurement: np.ndarray):
        projected_mean, projected_cov = self.project(mean, covariance)

        chol_factor, lower = np.linalg.cholesky(projected_cov, lower=True)
        kalman_gain = np.linalg.solve(chol_factor, self._update_mat @ covariance.T).T
        kalman_gain = np.linalg.solve(chol_factor.T, kalman_gain.T).T

        innovation = measurement - projected_mean

        new_mean = mean + innovation @ kalman_gain.T
        new_covariance = covariance - kalman_gain @ projected_cov @ kalman_gain.T
        return new_mean, new_covariance

    def multi_predict(self, mean: np.ndarray, covariance: np.ndarray):
        """批量预测"""
        std_pos = [
            self._std_weight_position * mean[:, 2],
            self._std_weight_position * mean[:, 3],
            self._std_weight_position * mean[:, 2],
            self._std_weight_position * mean[:, 3],
        ]
        std_vel = [
            self._std_weight_velocity * mean[:, 2],
            self._std_weight_velocity * mean[:, 3],
            self._std_weight_velocity * mean[:, 2],
            self._std_weight_velocity * mean[:, 3],
        ]
        sqr = np.square(np.r_[std_pos, std_vel]).T
        motion_cov = []
        for i in range(len(mean)):
            motion_cov.append(np.diag(sqr[i]))
        motion_cov = np.asarray(motion_cov)

        mean = np.dot(mean, self._motion_mat.T)
        left = np.expand_dims(self._motion_mat, 0)
        right = np.expand_dims(covariance, 0)
        covariance = np.dot(left, np.dot(right, left.T)).squeeze(0) + motion_cov

        return mean, covariance


def iou_batch(bboxes1: np.ndarray, bboxes2: np.ndarray) -> np.ndarray:
    """计算 IoU"""
    bboxes1 = np.expand_dims(bboxes1, 1)
    bboxes2 = np.expand_dims(bboxes2, 0)

    xx1 = np.maximum(bboxes1[..., 0], bboxes2[..., 0])
    yy1 = np.maximum(bboxes1[..., 1], bboxes2[..., 1])
    xx2 = np.minimum(bboxes1[..., 2], bboxes2[..., 2])
    yy2 = np.minimum(bboxes1[..., 3], bboxes2[..., 3])

    w = np.maximum(0.0, xx2 - xx1)
    h = np.maximum(0.0, yy2 - yy1)
    inter_area = w * h

    area1 = (bboxes1[..., 2] - bboxes1[..., 0]) * (bboxes1[..., 3] - bboxes1[..., 1])
    area2 = (bboxes2[..., 2] - bboxes2[..., 0]) * (bboxes2[..., 3] - bboxes2[..., 1])

    iou = inter_area / (area1 + area2 - inter_area + 1e-6)
    return iou


def linear_assignment(cost_matrix: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """线性分配"""
    try:
        from scipy.optimize import linear_sum_assignment
        x, y = linear_sum_assignment(cost_matrix)
        return np.array(list(zip(x, y)))
    except ImportError:
        # 简单贪心算法
        matches = []
        unmatched_rows = list(range(cost_matrix.shape[0]))
        unmatched_cols = list(range(cost_matrix.shape[1]))

        while unmatched_rows and unmatched_cols:
            min_val = np.inf
            min_row, min_col = -1, -1
            for r in unmatched_rows:
                for c in unmatched_cols:
                    if cost_matrix[r, c] < min_val:
                        min_val = cost_matrix[r, c]
                        min_row, min_col = r, c
            if min_row >= 0 and min_col >= 0:
                matches.append([min_row, min_col])
                unmatched_rows.remove(min_row)
                unmatched_cols.remove(min_col)

        return np.array(matches), np.array(unmatched_rows)


class TrackState:
    Tentative = 1
    Confirmed = 2
    Deleted = 3
    Tracked = 4
    Lost = 5


class BaseTrack:
    _count = 0

    def __init__(self):
        self.track_id = 0
        self.is_activated = False
        self.state = TrackState.Tentative
        self.history = deque(maxlen=30)
        self.features = []
        self.curr_feature = None
        self.score = 0
        self.start_frame = 0
        self.frame_id = 0
        self.time_since_update = 0

    @property
    def end_frame(self):
        return self.frame_id

    @staticmethod
    def next_id():
        BaseTrack._count += 1
        return BaseTrack._count

    def activate(self, *args):
        raise NotImplementedError

    def predict(self):
        raise NotImplementedError

    def update(self, *args, **kwargs):
        raise NotImplementedError

    def mark_lost(self):
        self.state = TrackState.Deleted

    def mark_removed(self):
        self.state = TrackState.Deleted


class STrack(BaseTrack):
    shared_kalman = KalmanFilterXYAH()

    def __init__(self, tlwh: np.ndarray, score: float):
        super().__init__()
        self._tlwh = np.asarray(tlwh, dtype=np.float32)
        self.kalman_filter = None
        self.mean, self.covariance = None, None
        self.is_activated = False
        self.score = score
        self.tracklet_len = 0

    def predict(self):
        mean_state = self.mean.copy()
        if self.state != TrackState.Tracked:
            mean_state[6] = 0
            mean_state[7] = 0
        self.mean, self.covariance = self.kalman_filter.predict(mean_state, self.covariance)

    @staticmethod
    def multi_predict(stracks: List['STrack']):
        if len(stracks) > 0:
            multi_mean = np.asarray([st.mean.copy() for st in stracks])
            multi_covariance = np.asarray([st.covariance for st in stracks])
            for i, st in enumerate(stracks):
                if st.state != TrackState.Tracked:
                    multi_mean[i][6] = 0
                    multi_mean[i][7] = 0
            multi_mean, multi_covariance = STrack.shared_kalman.multi_predict(multi_mean, multi_covariance)
            for i, (mean, cov) in enumerate(zip(multi_mean, multi_covariance)):
                stracks[i].mean = mean
                stracks[i].covariance = cov

    def activate(self, kalman_filter: KalmanFilterXYAH, frame_id: int):
        self.kalman_filter = kalman_filter
        self.track_id = self.next_id()
        self.mean, self.covariance = self.kalman_filter.initiate(self.tlwh_to_xyah(self._tlwh))

        self.tracklet_len = 0
        self.state = TrackState.Tracked
        if self.score >= 0.6:
            self.is_activated = True
        self.frame_id = frame_id
        self.start_frame = frame_id

    def re_activate(self, new_track: 'STrack', frame_id: int, new_id: bool = False):
        self.mean, self.covariance = self.kalman_filter.update(
            self.mean, self.covariance, self.tlwh_to_xyah(new_track.tlwh)
        )
        self.tracklet_len = 0
        self.state = TrackState.Tracked
        self.is_activated = True
        self.frame_id = frame_id
        if new_id:
            self.track_id = self.next_id()
        self.score = new_track.score

    def update(self, new_track: 'STrack', frame_id: int):
        self.frame_id = frame_id
        self.tracklet_len += 1

        new_tlwh = new_track.tlwh
        self.mean, self.covariance = self.kalman_filter.update(
            self.mean, self.covariance, self.tlwh_to_xyah(new_tlwh)
        )
        self.state = TrackState.Tracked
        self.is_activated = True
        self.score = new_track.score

    @property
    def tlwh(self) -> np.ndarray:
        if self.mean is None:
            return self._tlwh.copy()
        ret = self.mean[:4].copy()
        ret[2] *= ret[3]
        ret[:2] -= ret[2:] / 2
        return ret

    @property
    def tlbr(self) -> np.ndarray:
        ret = self.tlwh.copy()
        ret[2:] += ret[:2]
        return ret

    @staticmethod
    def tlwh_to_xyah(tlwh: np.ndarray) -> np.ndarray:
        ret = np.asarray(tlwh).copy()
        ret[:2] += ret[2:] / 2
        ret[2] /= ret[3]
        return ret

    def __repr__(self):
        return f'OT_{self.track_id}_({self.start_frame}-{self.end_frame})'


class BYTETracker:
    def __init__(self, args=None):
        self.tracked_stracks: List[STrack] = []
        self.lost_stracks: List[STrack] = []
        self.removed_stracks: List[STrack] = []
        self.frame_id = 0

        self.track_thresh = 0.3 if args is None else args.track_thresh
        self.match_thresh = 0.8 if args is None else args.match_thresh
        self.track_buffer = 30 if args is None else args.track_buffer

        self.max_time_lost = self.track_buffer
        self.kalman_filter = KalmanFilterXYAH()

    def update(self, dets: np.ndarray, img: np.ndarray = None):
        self.frame_id += 1

        activated_stracks = []
        refind_stracks = []
        lost_stracks = []
        removed_stracks = []

        if len(dets) == 0:
            # 没有检测结果
            unconfirmed = []
            tracked_stracks = []
            for track in self.tracked_stracks:
                if not track.is_activated:
                    unconfirmed.append(track)
                else:
                    tracked_stracks.append(track)

            strack_pool = self.joint_stracks(tracked_stracks, self.lost_stracks)
            STrack.multi_predict(strack_pool)

            for track in unconfirmed:
                track.mark_removed()
                removed_stracks.append(track)

            for track in strack_pool:
                if track.state == TrackState.Tracked:
                    track.mark_lost()
                    lost_stracks.append(track)

            self.tracked_stracks = [t for t in self.tracked_stracks if t.state == TrackState.Tracked]
            self.lost_stracks = self.sub_stracks(self.lost_stracks, self.tracked_stracks)
            self.lost_stracks.extend(lost_stracks)
            self.lost_stracks = self.sub_stracks(self.lost_stracks, self.removed_stracks)
            self.removed_stracks.extend(removed_stracks)
            self.tracked_stracks, self.lost_stracks = self.remove_duplicate_stracks(
                self.tracked_stracks, self.lost_stracks
            )

            output_stracks = [track for track in self.tracked_stracks if track.is_activated]
            return output_stracks

        scores = dets[:, 4]
        bboxes = dets[:, :4]

        remain_inds = scores > self.track_thresh
        inds_low = scores > 0.1
        inds_high = scores < self.track_thresh

        inds_second = np.logical_and(inds_low, inds_high)
        dets_second = bboxes[inds_second]
        dets = bboxes[remain_inds]
        scores_keep = scores[remain_inds]
        scores_second = scores[inds_second]

        if len(dets) > 0:
            detections = [STrack(self.tlbr_to_tlwh(tlbr), s) for tlbr, s in zip(dets, scores_keep)]
        else:
            detections = []

        unconfirmed = []
        tracked_stracks = []
        for track in self.tracked_stracks:
            if not track.is_activated:
                unconfirmed.append(track)
            else:
                tracked_stracks.append(track)

        strack_pool = self.joint_stracks(tracked_stracks, self.lost_stracks)
        STrack.multi_predict(strack_pool)

        dists = self.iou_distance(strack_pool, detections)
        matches, u_track, u_detection = self.linear_assignment(dists, thresh=self.match_thresh)

        for itracked, idet in matches:
            track = strack_pool[itracked]
            det = detections[idet]
            if track.state == TrackState.Tracked:
                track.update(det, self.frame_id)
                activated_stracks.append(track)
            else:
                track.re_activate(det, self.frame_id, new_id=False)
                refind_stracks.append(track)

        if len(dets_second) > 0:
            detections_second = [STrack(self.tlbr_to_tlwh(tlbr), s) for tlbr, s in zip(dets_second, scores_second)]
        else:
            detections_second = []

        r_tracked_stracks = [strack_pool[i] for i in u_track if strack_pool[i].state == TrackState.Tracked]
        dists = self.iou_distance(r_tracked_stracks, detections_second)
        matches, u_track, u_detection_second = self.linear_assignment(dists, thresh=0.5)

        for itracked, idet in matches:
            track = r_tracked_stracks[itracked]
            det = detections_second[idet]
            if track.state == TrackState.Tracked:
                track.update(det, self.frame_id)
                activated_stracks.append(track)
            else:
                track.re_activate(det, self.frame_id, new_id=False)
                refind_stracks.append(track)

        for it in u_track:
            track = r_tracked_stracks[it]
            if track.state != TrackState.Lost:
                track.mark_lost()
                lost_stracks.append(track)

        detections = [detections[i] for i in u_detection]
        dists = self.iou_distance(unconfirmed, detections)
        matches, u_unconfirmed, u_detection = self.linear_assignment(dists, thresh=0.7)

        for itracked, idet in matches:
            unconfirmed[itracked].update(detections[idet], self.frame_id)
            activated_stracks.append(unconfirmed[itracked])

        for it in u_unconfirmed:
            track = unconfirmed[it]
            track.mark_removed()
            removed_stracks.append(track)

        for inew in u_detection:
            track = detections[inew]
            if track.score < 0.6:
                continue
            track.activate(self.kalman_filter, self.frame_id)
            activated_stracks.append(track)

        self.tracked_stracks = [t for t in self.tracked_stracks if t.state == TrackState.Tracked]
        self.tracked_stracks = self.joint_stracks(self.tracked_stracks, activated_stracks)
        self.tracked_stracks = self.joint_stracks(self.tracked_stracks, refind_stracks)
        self.lost_stracks = self.sub_stracks(self.lost_stracks, self.tracked_stracks)
        self.lost_stracks.extend(lost_stracks)
        self.lost_stracks = self.sub_stracks(self.lost_stracks, self.removed_stracks)
        self.removed_stracks.extend(removed_stracks)
        self.tracked_stracks, self.lost_stracks = self.remove_duplicate_stracks(
            self.tracked_stracks, self.lost_stracks
        )

        output_stracks = [track for track in self.tracked_stracks if track.is_activated]
        return output_stracks

    @staticmethod
    def tlbr_to_tlwh(tlbr: np.ndarray) -> np.ndarray:
        ret = np.asarray(tlbr).copy()
        ret[2:] -= ret[:2]
        return ret

    def iou_distance(self, atracks: List[STrack], btracks: List[STrack]) -> np.ndarray:
        if len(atracks) > 0 and isinstance(atracks[0], np.ndarray):
            atlbrs = atracks
        else:
            atlbrs = [track.tlbr for track in atracks]

        if len(btracks) > 0 and isinstance(btracks[0], np.ndarray):
            btlbrs = btracks
        else:
            btlbrs = [track.tlbr for track in btracks]

        if len(atlbrs) == 0 or len(btlbrs) == 0:
            return np.zeros((len(atlbrs), len(btlbrs)))

        _ious = iou_batch(np.asarray(atlbrs), np.asarray(btlbrs))
        cost_matrix = 1 - _ious
        return cost_matrix

    def linear_assignment(self, cost_matrix: np.ndarray, thresh: float = 0.8):
        if cost_matrix.size == 0:
            return np.empty((0, 2), dtype=int), tuple(range(cost_matrix.shape[0])), tuple(range(cost_matrix.shape[1]))

        matches, unmatched_a, unmatched_b = [], [], []
        try:
            from scipy.optimize import linear_sum_assignment
            a_ind, b_ind = linear_sum_assignment(cost_matrix)
            matched_indices = np.array(list(zip(a_ind, b_ind)))

            for m in matched_indices:
                if cost_matrix[m[0], m[1]] > thresh:
                    unmatched_a.append(m[0])
                    unmatched_b.append(m[1])
                else:
                    matches.append(m)

            matches = np.array(matches)
            unmatched_a = list(set(range(cost_matrix.shape[0])) - set(matches[:, 0]))
            unmatched_b = list(set(range(cost_matrix.shape[1])) - set(matches[:, 1]))

        except ImportError:
            # 简单贪心匹配
            cost_matrix_copy = cost_matrix.copy()
            while True:
                min_val = np.min(cost_matrix_copy)
                if min_val > thresh:
                    break
                min_pos = np.unravel_index(np.argmin(cost_matrix_copy), cost_matrix_copy.shape)
                matches.append([min_pos[0], min_pos[1]])
                cost_matrix_copy[min_pos[0], :] = np.inf
                cost_matrix_copy[:, min_pos[1]] = np.inf

            matches = np.array(matches) if matches else np.empty((0, 2), dtype=int)
            unmatched_a = list(set(range(cost_matrix.shape[0])) - set(matches[:, 0]) if len(matches) > 0 else [])
            unmatched_b = list(set(range(cost_matrix.shape[1])) - set(matches[:, 1]) if len(matches) > 0 else [])

        return matches, unmatched_a, unmatched_b

    @staticmethod
    def joint_stracks(tlista: List[STrack], tlistb: List[STrack]) -> List[STrack]:
        exists = {}
        res = []
        for t in tlista:
            exists[t.track_id] = 1
            res.append(t)
        for t in tlistb:
            tid = t.track_id
            if not exists.get(tid, 0):
                exists[tid] = 1
                res.append(t)
        return res

    @staticmethod
    def sub_stracks(tlista: List[STrack], tlistb: List[STrack]) -> List[STrack]:
        stracks = {t.track_id: t for t in tlista}
        for t in tlistb:
            tid = t.track_id
            if stracks.get(tid, 0):
                del stracks[tid]
        return list(stracks.values())

    @staticmethod
    def remove_duplicate_stracks(stracksa: List[STrack], stracksb: List[STrack]) -> Tuple[List[STrack], List[STrack]]:
        pdist = iou_batch(np.asarray([t.tlbr for t in stracksa]), np.asarray([t.tlbr for t in stracksb]))
        pairs = np.where(pdist < 0.15)
        dupa, dupb = [], []
        for p, q in zip(*pairs):
            timep = stracksa[p].frame_id - stracksa[p].start_frame
            timeq = stracksb[q].frame_id - stracksb[q].start_frame
            if timep > timeq:
                dupb.append(q)
            else:
                dupa.append(p)
        resa = [t for i, t in enumerate(stracksa) if i not in dupa]
        resb = [t for i, t in enumerate(stracksb) if i not in dupb]
        return resa, resb
