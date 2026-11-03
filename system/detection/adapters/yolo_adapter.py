# -*- coding: utf-8 -*-
# ! python3

"""
Standalone YOLO architecture adapter for Ultralytics YOLOv8-YOLO26 and TensorRT engines.
Fully independent of legacy detection code.
"""

from __future__ import annotations

import gc
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import numpy as np
from numpy import ndarray

try:
    import torch
except ImportError:
    torch = None

try:
    from ultralytics import YOLO, settings

    try:
        from ultralytics.nn.backends import tensorrt as trt_backend

        trt_backend.TORCH_1_10 = False
    except Exception:
        pass
    _ULTRALYTICS_AVAILABLE = True
except ImportError:
    YOLO = None
    settings = None
    _ULTRALYTICS_AVAILABLE = False

from system.detection.exceptions import ModelLoadingError, ModelNotFoundError
from system.detection.interface import IDetector, ModelInfo
from system.detection.result import Detection, DetectionFrameResult
from system.utils.inference_devices import DEVICE_AUTO, normalize_device
from system.utils.logger import Logger

logger = Logger()


class YOLOAdapter(IDetector):
    """
    Ultralytics YOLO adapter supporting PyTorch (.pt) and TensorRT (.engine) models.
    Provides automatic fallback to PyTorch weights if a TensorRT engine fails.
    """

    def __init__(self) -> None:
        self.model: Optional[Any] = None
        self.weights_path: Optional[str] = None
        self.confidence: float = 0.5
        self.iou: float = 0.7
        self.device: str = "cpu"
        self.vid_stride: int = 1
        self.classes_list: Optional[List[int]] = None
        self.verbose: bool = False
        self._classes_map: Dict[int, str] = {}

        if settings is not None:
            try:
                settings.update({"sync": False})
            except Exception:
                pass

    def is_loaded(self) -> bool:
        """Check if model is currently loaded."""
        return self.model is not None

    def model_info(self) -> ModelInfo:
        """Return standardized runtime model info."""
        path_obj = Path(self.weights_path) if self.weights_path else None
        model_name = path_obj.stem if path_obj else "yolo"
        variant = path_obj.suffix.lower().lstrip(".") if path_obj else ""

        return ModelInfo(
            architecture="yolo",
            model_name=model_name,
            model_variant=variant,
            weights_path=self.weights_path,
            device=str(self.device),
            active_provider="tensorrt" if variant in ("engine", "trt") else "pytorch",
            inference_backend="ultralytics",
            num_classes=len(self._classes_map),
            classes=dict(self._classes_map),
            confidence=self.confidence,
            iou=self.iou,
            is_loaded=self.is_loaded(),
        )

    @staticmethod
    def _resolve_device(device_val: object) -> Union[int, str]:
        """Normalize configured device value for ultralytics."""
        if device_val is None or str(device_val).strip() == "":
            return ""
        normalized = normalize_device(device_val, "yolo")
        return "" if normalized == DEVICE_AUTO else normalized

    @staticmethod
    def find_fallback_weights(weights: Optional[Union[str, Path]]) -> Optional[str]:
        """
        Find fallback PyTorch weights (.pt) when a TensorRT engine fails.
        """
        if not weights:
            return None
        weights_path = Path(weights)
        if weights_path.suffix.lower() in (".engine", ".trt"):
            pt_path = weights_path.with_suffix(".pt")
            if pt_path.is_file():
                return str(pt_path)
            # Try searching in same folder for stem matching
            for candidate in weights_path.parent.glob("*.pt"):
                if candidate.stem.startswith(weights_path.stem):
                    return str(candidate)
        return None

    def load_model(self, weights: Union[str, Path], **kwargs: Any) -> None:
        """
        Load YOLO weights from file.

        Args:
            weights: Path to .pt or .engine weights file.
            **kwargs: confidence, iou, device, classes_list, verbose, etc.
        """
        if not _ULTRALYTICS_AVAILABLE or YOLO is None:
            raise ModelLoadingError("ultralytics package is not installed or available")

        path = Path(weights)
        if not path.is_file():
            raise ModelNotFoundError(f"Model weights file not found: {weights}")

        self.weights_path = str(path)
        self.confidence = float(kwargs.get("confidence", self.confidence))
        self.iou = float(kwargs.get("iou", self.iou))
        self.device = str(self._resolve_device(kwargs.get("device", self.device)))
        self.vid_stride = int(kwargs.get("vid_stride", self.vid_stride))
        self.classes_list = kwargs.get("classes_list", None)
        self.verbose = bool(kwargs.get("verbose", False))

        try:
            self.model = YOLO(self.weights_path)
            raw_names = getattr(self.model, "names", {})
            if isinstance(raw_names, dict):
                self._classes_map = {int(k): str(v) for k, v in raw_names.items()}
            elif isinstance(raw_names, (list, tuple)):
                self._classes_map = {i: str(v) for i, v in enumerate(raw_names)}
            else:
                self._classes_map = {}
        except Exception as exc:
            raise ModelLoadingError(f"Failed to load YOLO model from '{weights}': {exc}") from exc

    def unload(self) -> None:
        """Release YOLO model and free CUDA memory."""
        self.model = None
        self.weights_path = None
        self._classes_map.clear()

        if torch is not None and torch.cuda.is_available():
            try:
                torch.cuda.empty_cache()
            except Exception:
                pass
        gc.collect()

    def detect(self, image: ndarray, **kwargs: Any) -> DetectionFrameResult:
        """
        Run object detection inference on a frame.

        Args:
            image: Input image array in BGR format (H, W, C).
            **kwargs: Dynamic overrides for confidence, iou, etc.

        Returns:
            DetectionFrameResult: Standardized detection result DTO.
        """
        if self.model is None:
            raise ModelNotFoundError("YOLO model is not loaded")

        conf = float(kwargs.get("confidence", self.confidence))
        iou = float(kwargs.get("iou", self.iou))
        classes = kwargs.get("classes_list", self.classes_list)
        verbose = bool(kwargs.get("verbose", self.verbose))

        h, w = image.shape[:2]
        start_time = time.perf_counter()

        try:
            results = self.model.predict(
                image,
                conf=conf,
                iou=iou,
                device=self.device,
                vid_stride=self.vid_stride,
                classes=classes,
                verbose=verbose,
            )
        except Exception as exc:
            if torch is not None and torch.cuda.is_available():
                try:
                    torch.cuda.empty_cache()
                except Exception:
                    pass

            # TensorRT engine execution fallback to PyTorch weights
            if self.weights_path and Path(self.weights_path).suffix.lower() in (".engine", ".trt"):
                fallback = self.find_fallback_weights(self.weights_path)
                if fallback:
                    logger.warning(f"TensorRT execution failed ({exc}). Falling back to '{fallback}'...")
                    self.load_model(
                        fallback,
                        confidence=conf,
                        iou=iou,
                        device=self.device,
                        vid_stride=self.vid_stride,
                        classes_list=classes,
                        verbose=verbose,
                    )
                    results = self.model.predict(
                        image,
                        conf=conf,
                        iou=iou,
                        device=self.device,
                        vid_stride=self.vid_stride,
                        classes=classes,
                        verbose=verbose,
                    )
                else:
                    raise
            else:
                raise

        inference_time = time.perf_counter() - start_time
        detections: List[Detection] = []

        if results and len(results) > 0 and results[0].boxes is not None and len(results[0].boxes) > 0:
            boxes = results[0].boxes
            if hasattr(boxes, "data") and boxes.data is not None:
                data = boxes.data.cpu().numpy()
                boxes_xyxy = data[:, :4]
                confidences = data[:, 4]
                class_ids = data[:, 5].astype(int)
            else:
                boxes_xyxy = boxes.xyxy.cpu().numpy()
                confidences = boxes.conf.cpu().numpy()
                class_ids = boxes.cls.cpu().numpy().astype(int)

            for i in range(len(boxes_xyxy)):
                cid = int(class_ids[i])
                cname = self._classes_map.get(cid, str(cid))
                detections.append(
                    Detection(
                        class_id=cid,
                        class_name=cname,
                        confidence=float(confidences[i]),
                        x1=float(boxes_xyxy[i, 0]),
                        y1=float(boxes_xyxy[i, 1]),
                        x2=float(boxes_xyxy[i, 2]),
                        y2=float(boxes_xyxy[i, 3]),
                    )
                )

        return DetectionFrameResult(
            detections=detections,
            model_name=Path(self.weights_path).stem if self.weights_path else "yolo",
            inference_backend="ultralytics",
            inference_time=inference_time,
            image_width=w,
            image_height=h,
        )


# Backward-compatible alias for existing imports
UltralyticsYOLOAdapter = YOLOAdapter

__all__ = ["YOLOAdapter", "UltralyticsYOLOAdapter"]

