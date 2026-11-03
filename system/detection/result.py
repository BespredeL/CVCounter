# -*- coding: utf-8 -*-
# ! python3

"""
Unified Detection Result format for CVCounter.
Provides standard Detection and DetectionFrameResult structures with coordinate normalization,
validation, clamping, and full backward compatibility with legacy 3-tuple detection outputs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, List, Optional, Sequence, Tuple
import numpy as np


@dataclass(slots=True)
class Detection:
    """Individual object detection within a frame."""

    class_id: int
    class_name: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float

    def __post_init__(self) -> None:
        self.class_id = int(self.class_id)
        self.class_name = str(self.class_name) if self.class_name is not None else ""
        self.confidence = float(self.confidence)
        # Ensure coordinate ordering x1 <= x2 and y1 <= y2
        x1_val = float(self.x1)
        x2_val = float(self.x2)
        y1_val = float(self.y1)
        y2_val = float(self.y2)
        self.x1 = min(x1_val, x2_val)
        self.x2 = max(x1_val, x2_val)
        self.y1 = min(y1_val, y2_val)
        self.y2 = max(y1_val, y2_val)

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center(self) -> tuple[float, float]:
        return (self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0

    def to_xyxy(self) -> list[float]:
        return [self.x1, self.y1, self.x2, self.y2]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def clip(self, max_width: float, max_height: float) -> Detection:
        """Clamp box coordinates to [0, max_width] and [0, max_height]."""
        clamped_x1 = max(0.0, min(self.x1, float(max_width)))
        clamped_y1 = max(0.0, min(self.y1, float(max_height)))
        clamped_x2 = max(0.0, min(self.x2, float(max_width)))
        clamped_y2 = max(0.0, min(self.y2, float(max_height)))
        return Detection(
            class_id=self.class_id,
            class_name=self.class_name,
            confidence=self.confidence,
            x1=clamped_x1,
            y1=clamped_y1,
            x2=clamped_x2,
            y2=clamped_y2,
        )


@dataclass
class DetectionFrameResult:
    """Complete detection result for an image or frame with metadata."""

    detections: list[Detection] = field(default_factory=list)
    model_name: str = ""
    model_version: str = "1.0.0"
    inference_backend: str = "pytorch"
    inference_time: float = 0.0  # seconds
    image_width: int = 0
    image_height: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.detections)

    def __iter__(self):
        return iter(self.detections)

    def __getitem__(self, index: int) -> Detection:
        return self.detections[index]

    @property
    def inference_time_ms(self) -> float:
        return self.inference_time * 1000.0

    @property
    def is_empty(self) -> bool:
        return len(self.detections) == 0

    @property
    def boxes_xyxy(self) -> np.ndarray:
        """Return (N, 4) numpy array of bounding boxes."""
        if not self.detections:
            return np.empty((0, 4), dtype=np.float32)
        return np.array([d.to_xyxy() for d in self.detections], dtype=np.float32)

    @property
    def confidences(self) -> np.ndarray:
        """Return (N,) numpy array of confidence scores."""
        if not self.detections:
            return np.empty((0,), dtype=np.float32)
        return np.array([d.confidence for d in self.detections], dtype=np.float32)

    @property
    def classes(self) -> np.ndarray:
        """Return (N,) numpy array of integer class IDs."""
        if not self.detections:
            return np.empty((0,), dtype=int)
        return np.array([d.class_id for d in self.detections], dtype=int)

    def to_tracker_array(self) -> np.ndarray:
        """
        Return (N, 6) numpy array [x1, y1, x2, y2, score, class_id]
        ready for direct passing to trackers (ByteTrack, Sort).
        """
        if not self.detections:
            return np.empty((0, 6), dtype=np.float32)
        arr = np.empty((len(self.detections), 6), dtype=np.float32)
        for i, d in enumerate(self.detections):
            arr[i, 0] = d.x1
            arr[i, 1] = d.y1
            arr[i, 2] = d.x2
            arr[i, 3] = d.y2
            arr[i, 4] = d.confidence
            arr[i, 5] = float(d.class_id)
        return arr

    def to_legacy(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Convert to legacy CVCounter detector tuple: (boxes_xyxy, confidences, classes)."""
        return self.boxes_xyxy, self.confidences, self.classes

    def to_dict(self) -> dict[str, Any]:
        return {
            'model_name': self.model_name,
            'model_version': self.model_version,
            'inference_backend': self.inference_backend,
            'inference_time': self.inference_time,
            'inference_time_ms': self.inference_time_ms,
            'image_width': self.image_width,
            'image_height': self.image_height,
            'count': len(self.detections),
            'detections': [d.to_dict() for d in self.detections],
            'metadata': self.metadata,
        }

    def filter_by_confidence(self, min_confidence: float) -> DetectionFrameResult:
        """Filter detections by confidence threshold in-place and return self."""
        self.detections = [d for d in self.detections if d.confidence >= min_confidence]
        return self

    def filter_by_classes(self, allowed_classes: Optional[Iterable[int]]) -> DetectionFrameResult:
        """Filter detections to only include allowed class IDs."""
        if allowed_classes is None:
            return self
        allowed_set = {int(c) for c in allowed_classes}
        self.detections = [d for d in self.detections if d.class_id in allowed_set]
        return self

    def clip_to_image(self, width: Optional[int] = None, height: Optional[int] = None) -> DetectionFrameResult:
        """Clamp all detections to image dimensions."""
        w = width if width is not None else self.image_width
        h = height if height is not None else self.image_height
        if w > 0 and h > 0:
            clipped = []
            for d in self.detections:
                cd = d.clip(w, h)
                if cd.width > 0.0 and cd.height > 0.0:
                    clipped.append(cd)
            self.detections = clipped
        return self

    def suppress_duplicates(self, iou_threshold: float = 0.65) -> DetectionFrameResult:
        """
        Suppresses duplicate boxes across the same class using IoU.
        Safe for DETR models and avoids duplicate detections.
        """
        if len(self.detections) <= 1:
            return self

        # Group by class
        by_class: dict[int, list[Detection]] = {}
        for d in self.detections:
            by_class.setdefault(d.class_id, []).append(d)

        kept: list[Detection] = []
        for cid, group in by_class.items():
            # Sort descending by confidence
            group.sort(key=lambda x: x.confidence, reverse=True)
            class_kept: list[Detection] = []
            for candidate in group:
                overlap = False
                for existing in class_kept:
                    iou = _calc_iou(candidate, existing)
                    if iou > iou_threshold:
                        overlap = True
                        break
                if not overlap:
                    class_kept.append(candidate)
            kept.extend(class_kept)

        self.detections = kept
        return self

    @classmethod
    def empty(
        cls,
        model_name: str = "",
        model_version: str = "1.0.0",
        inference_backend: str = "pytorch",
        image_width: int = 0,
        image_height: int = 0,
    ) -> DetectionFrameResult:
        """Create an empty detection result."""
        return cls(
            detections=[],
            model_name=model_name,
            model_version=model_version,
            inference_backend=inference_backend,
            inference_time=0.0,
            image_width=image_width,
            image_height=image_height,
        )

    @classmethod
    def from_legacy(
        cls,
        legacy_result: tuple[np.ndarray, np.ndarray, np.ndarray],
        image_width: int,
        image_height: int,
        classes_map: Optional[dict[int, str]] = None,
        model_name: str = "legacy",
        model_version: str = "1.0.0",
        inference_backend: str = "unknown",
        inference_time: float = 0.0,
    ) -> DetectionFrameResult:
        """Construct DetectionFrameResult from legacy 3-tuple (boxes, confidences, classes)."""
        boxes, confs, clss = legacy_result
        cmap = classes_map or {}
        detections: list[Detection] = []
        if boxes is not None and len(boxes) > 0:
            for i in range(len(boxes)):
                box = boxes[i]
                conf = float(confs[i]) if confs is not None and i < len(confs) else 1.0
                cls_id = int(clss[i]) if clss is not None and i < len(clss) else 0
                cls_name = cmap.get(cls_id, f"class_{cls_id}")
                x1, y1, x2, y2 = float(box[0]), float(box[1]), float(box[2]), float(box[3])
                detections.append(
                    Detection(
                        class_id=cls_id,
                        class_name=cls_name,
                        confidence=conf,
                        x1=x1,
                        y1=y1,
                        x2=x2,
                        y2=y2,
                    )
                )

        result = cls(
            detections=detections,
            model_name=model_name,
            model_version=model_version,
            inference_backend=inference_backend,
            inference_time=inference_time,
            image_width=image_width,
            image_height=image_height,
        )
        result.clip_to_image()
        return result


def _calc_iou(b1: Detection, b2: Detection) -> float:
    """Calculate Intersection over Union for two detections."""
    x1 = max(b1.x1, b2.x1)
    y1 = max(b1.y1, b2.y1)
    x2 = min(b1.x2, b2.x2)
    y2 = min(b1.y2, b2.y2)

    inter_w = max(0.0, x2 - x1)
    inter_h = max(0.0, y2 - y1)
    inter_area = inter_w * inter_h

    area1 = b1.area
    area2 = b2.area
    union = area1 + area2 - inter_area
    if union <= 0.0:
        return 0.0
    return inter_area / union

