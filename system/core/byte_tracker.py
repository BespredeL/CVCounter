# -*- coding: utf-8 -*-
# ! python3

# Developed for CVCounterWEB
# ByteTrack: Multi-Object Tracking by Associating Every Detection Box
# High-performance, lightweight, rock-solid Kalman tracking with 2-stage association.

from __future__ import annotations

from typing import Optional
import numpy as np
from filterpy.kalman import KalmanFilter
from scipy.optimize import linear_sum_assignment


def convert_bbox_to_z(bbox: np.ndarray) -> np.ndarray:
    """
    Takes a bounding box in the form [x1, y1, x2, y2] and returns z in the form
    [x, y, s, r] where x, y is the center, s is the area (scale), and r is the aspect ratio.
    """
    w = max(1e-2, float(bbox[2] - bbox[0]))
    h = max(1e-2, float(bbox[3] - bbox[1]))
    x = float(bbox[0]) + w / 2.0
    y = float(bbox[1]) + h / 2.0
    s = w * h
    r = w / float(h)
    return np.array([x, y, s, r], dtype=np.float32).reshape((4, 1))


def convert_x_to_bbox(x: np.ndarray) -> np.ndarray:
    """
    Takes a bounding box in the center form [x, y, s, r] and returns it in the form
    [x1, y1, x2, y2] where x1, y1 is top-left and x2, y2 is bottom-right.
    """
    w = np.sqrt(max(1e-4, float(x[2] * x[3])))
    h = max(1e-2, float(x[2] / max(1e-4, w)))
    cx = float(x[0])
    cy = float(x[1])
    return np.array([cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0], dtype=np.float32).reshape((1, 4))


def iou_batch(bb_test: np.ndarray, bb_gt: np.ndarray) -> np.ndarray:
    """
    Computes pairwise IoU between two sets of bboxes in the form [x1, y1, x2, y2].
    bb_test: (N, 4)
    bb_gt: (M, 4)
    Returns: (N, M) matrix of IoU values between 0.0 and 1.0.
    """
    if len(bb_test) == 0 or len(bb_gt) == 0:
        return np.zeros((len(bb_test), len(bb_gt)), dtype=np.float32)

    bb_gt = np.expand_dims(bb_gt, 0)
    bb_test = np.expand_dims(bb_test, 1)

    xx1 = np.maximum(bb_test[..., 0], bb_gt[..., 0])
    yy1 = np.maximum(bb_test[..., 1], bb_gt[..., 1])
    xx2 = np.minimum(bb_test[..., 2], bb_gt[..., 2])
    yy2 = np.minimum(bb_test[..., 3], bb_gt[..., 3])

    w = np.maximum(0.0, xx2 - xx1)
    h = np.maximum(0.0, yy2 - yy1)
    wh = w * h

    area_test = np.maximum(0.0, bb_test[..., 2] - bb_test[..., 0]) * np.maximum(0.0, bb_test[..., 3] - bb_test[..., 1])
    area_gt = np.maximum(0.0, bb_gt[..., 2] - bb_gt[..., 0]) * np.maximum(0.0, bb_gt[..., 3] - bb_gt[..., 1])

    union = area_test + area_gt - wh
    union = np.maximum(union, 1e-6)
    return wh / union


class KalmanBoxTracker:
    """
    Kalman filter tracking individual object bounding boxes.
    Uses constant-velocity model with 7-dim state [x, y, s, r, vx, vy, vs].
    """
    count = 0

    def __init__(self, bbox: np.ndarray, class_id: int = 0):
        self.kf = KalmanFilter(dim_x=7, dim_z=4)
        self.kf.F = np.array([
            [1, 0, 0, 0, 1, 0, 0],
            [0, 1, 0, 0, 0, 1, 0],
            [0, 0, 1, 0, 0, 0, 1],
            [0, 0, 0, 1, 0, 0, 0],
            [0, 0, 0, 0, 1, 0, 0],
            [0, 0, 0, 0, 0, 1, 0],
            [0, 0, 0, 0, 0, 0, 1]
        ], dtype=np.float32)

        self.kf.H = np.array([
            [1, 0, 0, 0, 0, 0, 0],
            [0, 1, 0, 0, 0, 0, 0],
            [0, 0, 1, 0, 0, 0, 0],
            [0, 0, 0, 1, 0, 0, 0]
        ], dtype=np.float32)

        self.kf.R[2:, 2:] *= 10.0
        self.kf.P[4:, 4:] *= 1000.0  # High initial uncertainty on velocities
        self.kf.P *= 10.0
        self.kf.Q[-1, -1] *= 0.01
        self.kf.Q[4:, 4:] *= 0.01

        self.kf.x[:4] = convert_bbox_to_z(bbox)
        self.time_since_update = 0

        KalmanBoxTracker.count += 1
        self.id = KalmanBoxTracker.count

        self.hits = 1
        self.hit_streak = 1
        self.age = 0
        self.class_id = int(class_id)

    def update(self, bbox: np.ndarray, class_id: Optional[int] = None):
        """Update tracker state with a newly observed detection."""
        self.time_since_update = 0
        self.hits += 1
        self.hit_streak += 1
        self.kf.update(convert_bbox_to_z(bbox))
        if class_id is not None:
            self.class_id = int(class_id)

    def predict(self) -> np.ndarray:
        """Advance state prediction and return predicted [x1, y1, x2, y2]."""
        if (self.kf.x[6] + self.kf.x[2]) <= 0:
            self.kf.x[6] *= 0.0
        self.kf.predict()
        self.age += 1
        if self.time_since_update > 0:
            self.hit_streak = 0
        self.time_since_update += 1
        return convert_x_to_bbox(self.kf.x)[0]

    def get_state(self) -> np.ndarray:
        """Return current estimated bounding box [x1, y1, x2, y2]."""
        return convert_x_to_bbox(self.kf.x)[0]


class BYTETracker:
    """
    ByteTrack: Multi-Object Tracking by Associating Every Detection Box.
    Combines FilterPy Kalman Filter with ByteTrack's 2-stage association.

    Drop-in replacement for Sort with identical .update(dets) API.
    """
    def __init__(
            self,
            track_thresh: float = 0.45,
            match_thresh: float = 0.7,
            iou_threshold: Optional[float] = None,
            max_age: int = 30,
            min_hits: int = 3,
            **kwargs,
    ):
        self.track_thresh = float(track_thresh)
        # Support both min_iou style (e.g. 0.3) and distance cost style (e.g. 0.7/0.8):
        if iou_threshold is not None:
            self.min_iou = float(iou_threshold)
        elif float(match_thresh) > 0.5:
            # Caller passed distance cost threshold (e.g. 0.7 -> min_iou = 0.3)
            self.min_iou = max(0.1, 1.0 - float(match_thresh))
        else:
            # Caller passed min IoU threshold directly (e.g. 0.3)
            self.min_iou = float(match_thresh)

        self.max_age = int(max_age)
        self.min_hits = int(min_hits)
        self.trackers: list[KalmanBoxTracker] = []
        self.frame_count: int = 0

    def reset(self):
        """Reset internal tracker state."""
        self.trackers.clear()
        self.frame_count = 0
        KalmanBoxTracker.count = 0

    def update(self, dets: np.ndarray = np.empty((0, 6))) -> np.ndarray:
        """
        Process detections for current frame and return active tracks.

        Args:
            dets (np.ndarray): Detections array with shape (N, 5) or (N, 6):
                               [x1, y1, x2, y2, score, (optional) class_id]

        Returns:
            np.ndarray: Tracked objects with shape (M, 6):
                        [x1, y1, x2, y2, track_id, class_id]
        """
        self.frame_count += 1
        if dets is None or len(dets) == 0:
            dets = np.empty((0, 6), dtype=np.float32)

        # 1. Predict locations for all existing trackers
        trks = np.zeros((len(self.trackers), 4), dtype=np.float32)
        to_del = []
        for t, trk in enumerate(self.trackers):
            pos = trk.predict()
            if np.any(np.isnan(pos)) or np.any(np.isinf(pos)):
                to_del.append(t)
            else:
                trks[t, :] = pos

        for t in reversed(to_del):
            self.trackers.pop(t)
            trks = np.delete(trks, t, axis=0)

        # 2. Split detections into high-score and low-score (ByteTrack Core)
        scores = dets[:, 4] if dets.shape[1] > 4 else np.ones(len(dets), dtype=np.float32)
        high_mask = scores >= self.track_thresh
        low_mask = (scores < self.track_thresh) & (scores >= 0.1)

        dets_high = dets[high_mask]
        dets_low = dets[low_mask]

        # 3. First association: match high-score detections with existing trackers
        matched_trks_set: set[int] = set()
        unmatched_dets_high: list[int] = list(range(len(dets_high)))

        if len(dets_high) > 0 and len(self.trackers) > 0:
            iou_mat = iou_batch(dets_high[:, :4], trks)
            row_ind, col_ind = linear_sum_assignment(-iou_mat)
            for r, c in zip(row_ind, col_ind):
                if iou_mat[r, c] >= self.min_iou:
                    cls_val = dets_high[r, 5] if dets_high.shape[1] > 5 else None
                    self.trackers[c].update(dets_high[r, :4], cls_val)
                    matched_trks_set.add(c)
                    unmatched_dets_high.remove(r)

        # 4. Second association: match low-score detections with remaining unmatched trackers
        # (This rescues tracks occluded by objects or motion blur, preventing ID switches!)
        unmatched_trks = [t for t in range(len(self.trackers)) if t not in matched_trks_set]
        if len(dets_low) > 0 and len(unmatched_trks) > 0:
            iou_mat_low = iou_batch(dets_low[:, :4], trks[unmatched_trks])
            row_ind, col_ind = linear_sum_assignment(-iou_mat_low)
            # Low-score detections use a slightly more forgiving IoU threshold
            second_iou_thresh = max(0.15, self.min_iou * 0.7)
            for r, c in zip(row_ind, col_ind):
                trk_idx = unmatched_trks[c]
                if iou_mat_low[r, c] >= second_iou_thresh:
                    cls_val = dets_low[r, 5] if dets_low.shape[1] > 5 else None
                    self.trackers[trk_idx].update(dets_low[r, :4], cls_val)
                    matched_trks_set.add(trk_idx)

        # 5. Initialize new trackers from remaining unmatched high-score detections
        for r in unmatched_dets_high:
            cls_id = int(dets_high[r, 5]) if dets_high.shape[1] > 5 else 0
            self.trackers.append(KalmanBoxTracker(dets_high[r, :4], cls_id))

        # 6. Collect confirmed active tracks and purge dead tracks
        ret = []
        i = len(self.trackers)
        for trk in reversed(self.trackers):
            i -= 1
            d = trk.get_state()
            if (trk.time_since_update < 1) and (trk.hit_streak >= self.min_hits or self.frame_count <= self.min_hits):
                ret.append([d[0], d[1], d[2], d[3], trk.id, trk.class_id])
            if trk.time_since_update > self.max_age:
                self.trackers.pop(i)

        if len(ret) > 0:
            return np.array(ret, dtype=np.float32)
        return np.empty((0, 6), dtype=np.float32)


# Backwards compatibility aliases
ByteTrack = BYTETracker
Sort = BYTETracker

__all__ = ['BYTETracker', 'ByteTrack', 'Sort', 'KalmanBoxTracker']
