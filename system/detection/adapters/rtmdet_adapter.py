# -*- coding: utf-8 -*-
# ! python3

"""
RTMDet (Real-time Models for Object Detection) Adapter for CVCounter.
Provides integration with OpenMMLab MMDetection and MMDeploy ONNX models.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np

from system.detection.interface import IDetector, ModelInfo
from system.detection.result import Detection, DetectionFrameResult
from system.detection.adapters.rf_detr_adapter import COCO_CLASSES_80
from system.detection.exceptions import ModelLoadingError, ModelNotFoundError


class RTMDetAdapter(IDetector):
    """Adapter for OpenMMLab RTMDet object detection models."""

    SUPPORTED_VARIANTS = ("tiny", "small", "medium", "large", "extra_large")

    def __init__(self) -> None:
        self.model = None
        self.weights: Optional[str] = None
        self.config_path: Optional[str] = None
        self.variant: str = "tiny"
        self.confidence_threshold: float = 0.4
        self.device: str = "cpu"
        self.input_size: tuple[int, int] = (640, 640)
        self.backend: str = "pytorch"
        self.classes_map: dict[int, str] = dict(COCO_CLASSES_80)
        self.classes_list: Optional[list[int]] = None
        self._onnx_session = None

    def is_loaded(self) -> bool:
        return self.model is not None or self._onnx_session is not None

    def load(self, weights: str, **kwargs) -> None:
        self.weights = weights
        self.config_path = kwargs.get("config_path", kwargs.get("model_config_path"))
        self.confidence_threshold = float(kwargs.get("confidence", kwargs.get("conf", 0.4)))
        self.device = str(kwargs.get("device", "cpu")).lower()
        self.variant = str(kwargs.get("variant", kwargs.get("model_variant", "tiny"))).lower()
        self.classes_list = kwargs.get("classes_list", None)
        self.backend = str(kwargs.get("backend", "pytorch")).lower()

        insz = kwargs.get("input_size", (640, 640))
        if isinstance(insz, int):
            self.input_size = (insz, insz)
        elif isinstance(insz, (list, tuple)) and len(insz) == 2:
            self.input_size = (int(insz[0]), int(insz[1]))

        ext = Path(weights).suffix.lower() if weights else ""
        if ext == ".onnx" or self.backend in ("onnx", "onnxruntime"):
            self._load_onnx(weights)
            return

        # Attempt to load through MMDetection if installed
        try:
            from mmdet.apis import init_detector
        except ImportError:
            raise ModelLoadingError(
                "RTMDet PyTorch backend requires 'mmdet' and 'mmcv'. "
                "Install via: pip install openmim && mim install mmengine mmcv mmdet. "
                "Alternatively, load an exported RTMDet .onnx model directly via ONNX Runtime."
            )

        if not self.config_path or not Path(self.config_path).is_file():
            # Search for default configs if available
            cand = Path(f"config/models/rtmdet/rtmdet_{self.variant}_8xb32-300e_coco.py")
            if not cand.is_file():
                cand = Path(f"configs/models/rtmdet/rtmdet_{self.variant}_8xb32-300e_coco.py")
            if cand.is_file():
                self.config_path = str(cand)
            else:
                raise ModelLoadingError(
                    f"RTMDet requires a valid 'config_path' pointing to the model configuration file. "
                    f"Provided: {self.config_path}"
                )

        try:
            dev = self.device if "cuda" in self.device else "cpu"
            self.model = init_detector(self.config_path, weights, device=dev)
            if hasattr(self.model, "dataset_meta") and "classes" in self.model.dataset_meta:
                clss = self.model.dataset_meta["classes"]
                self.classes_map = {i: str(c) for i, c in enumerate(clss)}
        except Exception as e:
            raise ModelLoadingError(f"Failed to load RTMDet model: {e}") from e

    def _load_onnx(self, weights_path: str) -> None:
        from system.detection.backends.onnx import ONNXSession
        session = ONNXSession()
        session.load(weights_path, device=self.device)
        self._onnx_session = session
        self.backend = "onnx"

    def unload(self) -> None:
        self.model = None
        if self._onnx_session is not None:
            self._onnx_session.unload()
            self._onnx_session = None
        self.weights = None
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    def configure(self, **kwargs) -> None:
        if "confidence" in kwargs or "conf" in kwargs:
            self.confidence_threshold = float(kwargs.get("confidence", kwargs.get("conf", self.confidence_threshold)))
        if "device" in kwargs:
            self.device = str(kwargs.get("device")).lower()
        if "classes_list" in kwargs:
            self.classes_list = kwargs.get("classes_list")
        if "input_size" in kwargs:
            insz = kwargs.get("input_size")
            if isinstance(insz, int):
                self.input_size = (insz, insz)
            elif isinstance(insz, (list, tuple)) and len(insz) == 2:
                self.input_size = (int(insz[0]), int(insz[1]))

    def get_classes(self) -> dict[int, str]:
        return dict(self.classes_map)

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(
            architecture="rtmdet",
            model_name=Path(self.weights).stem if self.weights else f"rtmdet_{self.variant}",
            model_variant=self.variant,
            version="1.0.0",
            weights_path=self.weights,
            device=self.device,
            inference_backend=self.backend,
            num_classes=len(self.classes_map),
            classes=self.classes_map,
            input_size=self.input_size,
            parameters={
                'confidence': self.confidence_threshold,
                'variant': self.variant,
                'config_path': self.config_path,
                'author': 'OpenMMLab',
                'license': 'Apache 2.0',
            },
        )

    def predict(self, image: np.ndarray, **kwargs) -> DetectionFrameResult:
        if not self.is_loaded():
            raise ModelNotFoundError("RTMDet model is not loaded")

        h, w = image.shape[:2]
        t0 = time.perf_counter()
        conf_thresh = float(kwargs.get("confidence", kwargs.get("conf", self.confidence_threshold)))

        detections: list[Detection] = []

        if self._onnx_session is not None:
            # Process via ONNX Runtime (compatible with MMDeploy RTMDet ONNX export)
            from system.detection.transforms import create_blob
            from system.detection.postprocessing import parse_yolo_outputs
            blob = create_blob(image, self.input_size, {"resize": "letterbox"})
            outputs = self._onnx_session.predict(blob)

            boxes, confs, clss = parse_yolo_outputs(
                outputs,
                confidence=conf_thresh,
                iou=0.6,
                input_size=self.input_size,
                image_shape=(h, w),
                classes_list=self.classes_list,
            )
            for i in range(len(boxes)):
                cid = int(clss[i])
                cname = self.classes_map.get(cid, f"class_{cid}")
                detections.append(
                    Detection(
                        class_id=cid,
                        class_name=cname,
                        confidence=float(confs[i]),
                        x1=float(boxes[i][0]),
                        y1=float(boxes[i][1]),
                        x2=float(boxes[i][2]),
                        y2=float(boxes[i][3]),
                    )
                )
        else:
            # Process via MMDetection
            from mmdet.apis import inference_detector
            pred_result = inference_detector(self.model, image)
            pred_instances = pred_result.pred_instances
            scores = pred_instances.scores.cpu().numpy()
            labels = pred_instances.labels.cpu().numpy()
            bboxes = pred_instances.bboxes.cpu().numpy()

            for i in range(len(scores)):
                conf = float(scores[i])
                if conf < conf_thresh:
                    continue
                cid = int(labels[i])
                if self.classes_list is not None and cid not in self.classes_list:
                    continue

                box = bboxes[i]
                cname = self.classes_map.get(cid, f"class_{cid}")
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

        duration = time.perf_counter() - t0

        result = DetectionFrameResult(
            detections=detections,
            model_name=Path(self.weights).stem if self.weights else f"rtmdet_{self.variant}",
            model_version="1.0.0",
            inference_backend=self.backend,
            inference_time=duration,
            image_width=w,
            image_height=h,
        )
        result.clip_to_image()
        return result

    # Contract aliases
    load_model = load
    detect = predict
    model_info = get_model_info

