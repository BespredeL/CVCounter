# -*- coding: utf-8 -*-
# ! python3

"""
Ultralytics YOLO Adapter for CVCounter.
Preserves existing YOLO weights, formats, and runtime behavior while adhering
to the unified IDetector contract.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np

from system.detection.interface import IDetector, ModelInfo
from system.detection.result import Detection, DetectionFrameResult
from system.object_detection.object_detection_yolo import ObjectDetectionYOLO
from system.utils.inference_devices import normalize_device


class UltralyticsYOLOAdapter(IDetector):
    """IDetector implementation wrapping Ultralytics YOLO models."""

    def __init__(self) -> None:
        self._impl = ObjectDetectionYOLO()
        self.weights: Optional[str] = None
        self.confidence_threshold: float = 0.5
        self.iou_threshold: float = 0.7
        self.device: str = "cpu"
        self.input_size: tuple[int, int] = (640, 640)
        self.backend: str = "pytorch"
        self.classes_list: Optional[list[int]] = None

    def is_loaded(self) -> bool:
        return self._impl.model is not None

    def load(self, weights: str, **kwargs) -> None:
        self.weights = weights
        self.confidence_threshold = float(kwargs.get("confidence", kwargs.get("conf", 0.5)))
        self.iou_threshold = float(kwargs.get("iou", 0.7))
        self.device = str(kwargs.get("device", "cpu"))
        self.classes_list = kwargs.get("classes_list", None)
        self.backend = str(kwargs.get("backend", "pytorch")).lower()

        # Input size if provided
        insz = kwargs.get("input_size", (640, 640))
        if isinstance(insz, int):
            self.input_size = (insz, insz)
        elif isinstance(insz, (list, tuple)) and len(insz) == 2:
            self.input_size = (int(insz[0]), int(insz[1]))

        # Load through existing implementation
        self._impl.load_model(
            weights=weights,
            confidence=self.confidence_threshold,
            iou=self.iou_threshold,
            device=self.device,
            classes_list=self.classes_list,
            **kwargs,
        )

    def unload(self) -> None:
        self._impl.cleanup()
        self.weights = None

    def configure(self, **kwargs) -> None:
        if "confidence" in kwargs or "conf" in kwargs:
            self.confidence_threshold = float(kwargs.get("confidence", kwargs.get("conf", self.confidence_threshold)))
            self._impl.confidence = self.confidence_threshold
        if "iou" in kwargs:
            self.iou_threshold = float(kwargs.get("iou", self.iou_threshold))
            self._impl.iou = self.iou_threshold
        if "classes_list" in kwargs:
            self.classes_list = kwargs.get("classes_list")
            self._impl.classes_list = self.classes_list
        if "device" in kwargs:
            self.device = str(kwargs.get("device"))
            self._impl.device = self._impl._resolve_device(self.device)

    def get_classes(self) -> dict[int, str]:
        return self._impl.get_classes()

    def get_model_info(self) -> ModelInfo:
        classes_map = self.get_classes()
        w_path = Path(self.weights) if self.weights else None
        stem = w_path.stem if w_path else "yolo"
        variant = stem.replace("yolo", "").replace("v8", "").replace("11", "").replace("26", "")
        return ModelInfo(
            architecture="yolo",
            model_name=stem,
            model_variant=variant,
            version="8.4",
            weights_path=self.weights,
            device=self.device,
            inference_backend=self.backend,
            num_classes=len(classes_map),
            classes=classes_map,
            input_size=self.input_size,
            parameters={
                'confidence': self.confidence_threshold,
                'iou': self.iou_threshold,
            },
        )

    def predict(self, image: np.ndarray, **kwargs) -> DetectionFrameResult:
        if not self.is_loaded():
            raise RuntimeError("YOLO model is not loaded")

        h, w = image.shape[:2]
        t0 = time.perf_counter()

        # Run prediction
        boxes_xyxy, confs, clss = self._impl.detect(image, **kwargs)
        duration = time.perf_counter() - t0

        classes_map = self.get_classes()
        detections: list[Detection] = []

        if boxes_xyxy is not None and len(boxes_xyxy) > 0:
            for i in range(len(boxes_xyxy)):
                box = boxes_xyxy[i]
                conf = float(confs[i])
                cid = int(clss[i])
                cname = classes_map.get(cid, f"class_{cid}")
                detections.append(
                    Detection(
                        class_id=cid,
                        class_name=cname,
                        confidence=conf,
                        x1=float(box[0]),
                        y1=float(box[1]),
                        x2=float(box[2]),
                        y2=float(box[3]),
                    )
                )

        result = DetectionFrameResult(
            detections=detections,
            model_name=Path(self.weights).stem if self.weights else "yolo",
            model_version="ultralytics-8.4",
            inference_backend=self.backend,
            inference_time=duration,
            image_width=w,
            image_height=h,
        )
        result.clip_to_image()
        return result
