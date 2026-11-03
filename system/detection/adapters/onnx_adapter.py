# -*- coding: utf-8 -*-
# ! python3

"""
Generic ONNX Runtime Detector Adapter for CVCounter.
Provides unified IDetector interface over ONNX models with automatic decoder resolution.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np

from system.detection.interface import IDetector, ModelInfo
from system.detection.result import Detection, DetectionFrameResult
from system.object_detection.object_detection_onnx import ObjectDetectionONNX


class GenericONNXAdapter(IDetector):
    """Adapter wrapping ObjectDetectionONNX to implement IDetector."""

    def __init__(self) -> None:
        self._impl = ObjectDetectionONNX()
        self.weights: Optional[str] = None
        self.device: str = "cpu"
        self.confidence_threshold: float = 0.5
        self.iou_threshold: float = 0.7
        self.input_size: tuple[int, int] = (640, 640)

    def is_loaded(self) -> bool:
        return self._impl.session is not None

    def load(self, weights: str, **kwargs) -> None:
        self.weights = weights
        self.confidence_threshold = float(kwargs.get("confidence", kwargs.get("conf", 0.5)))
        self.iou_threshold = float(kwargs.get("iou", 0.7))
        self.device = str(kwargs.get("device", "cpu")).lower()

        insz = kwargs.get("input_size", (640, 640))
        if isinstance(insz, int):
            self.input_size = (insz, insz)
        elif isinstance(insz, (list, tuple)) and len(insz) == 2:
            self.input_size = (int(insz[0]), int(insz[1]))

        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"] if "cuda" in self.device else ["CPUExecutionProvider"]
        self._impl.load_model(
            weights=weights,
            confidence=self.confidence_threshold,
            iou=self.iou_threshold,
            input_size=self.input_size,
            providers=providers,
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
            self._impl.classes_list = kwargs.get("classes_list")

    def get_classes(self) -> dict[int, str]:
        return self._impl.get_classes()

    def get_model_info(self) -> ModelInfo:
        classes_map = self.get_classes()
        w_path = Path(self.weights) if self.weights else None
        stem = w_path.stem if w_path else "onnx_model"
        return ModelInfo(
            architecture="onnx",
            model_name=stem,
            version="1.0.0",
            weights_path=self.weights,
            device=self.device,
            inference_backend="onnx",
            num_classes=len(classes_map),
            classes=classes_map,
            input_size=self.input_size,
            parameters={
                'confidence': self.confidence_threshold,
                'iou': self.iou_threshold,
                'decoder': self._impl.decoder,
            },
        )

    def predict(self, image: np.ndarray, **kwargs) -> DetectionFrameResult:
        if not self.is_loaded():
            raise RuntimeError("ONNX model is not loaded")

        h, w = image.shape[:2]
        t0 = time.perf_counter()
        boxes_xyxy, confs, clss = self._impl.detect(image, **kwargs)
        duration = time.perf_counter() - t0

        classes_map = self.get_classes()
        detections: list[Detection] = []

        if boxes_xyxy is not None and len(boxes_xyxy) > 0:
            for i in range(len(boxes_xyxy)):
                cid = int(clss[i])
                cname = classes_map.get(cid, f"class_{cid}")
                detections.append(
                    Detection(
                        class_id=cid,
                        class_name=cname,
                        confidence=float(confs[i]),
                        x1=float(boxes_xyxy[i][0]),
                        y1=float(boxes_xyxy[i][1]),
                        x2=float(boxes_xyxy[i][2]),
                        y2=float(boxes_xyxy[i][3]),
                    )
                )

        result = DetectionFrameResult(
            detections=detections,
            model_name=Path(self.weights).stem if self.weights else "onnx_model",
            model_version="1.0.0",
            inference_backend="onnx",
            inference_time=duration,
            image_width=w,
            image_height=h,
        )
        result.clip_to_image()
        return result
