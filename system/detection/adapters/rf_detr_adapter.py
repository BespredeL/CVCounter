# -*- coding: utf-8 -*-
# ! python3

"""
RF-DETR (Real-Time Detection Transformer) Adapter for CVCounter.
Provides integration with Roboflow RF-DETR (Nano, Small, Medium, Large)
for PyTorch (CUDA/CPU) and ONNX Runtime inference.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np

from system.detection.interface import IDetector, ModelInfo
from system.detection.result import Detection, DetectionFrameResult
from system.utils.exception_handler import ModelLoadingError, ModelNotFoundError

COCO_CLASSES_80 = {
    0: "person", 1: "bicycle", 2: "car", 3: "motorcycle", 4: "airplane", 5: "bus",
    6: "train", 7: "truck", 8: "boat", 9: "traffic light", 10: "fire hydrant",
    11: "stop sign", 12: "parking meter", 13: "bench", 14: "bird", 15: "cat",
    16: "dog", 17: "horse", 18: "sheep", 19: "cow", 20: "elephant", 21: "bear",
    22: "zebra", 23: "giraffe", 24: "backpack", 25: "umbrella", 26: "handbag",
    27: "tie", 28: "suitcase", 29: "frisbee", 30: "skis", 31: "snowboard",
    32: "sports ball", 33: "kite", 34: "baseball bat", 35: "baseball glove",
    36: "skateboard", 37: "surfboard", 38: "tennis racket", 39: "bottle",
    40: "wine glass", 41: "cup", 42: "fork", 43: "knife", 44: "spoon",
    45: "bowl", 46: "banana", 47: "apple", 48: "sandwich", 49: "orange",
    50: "broccoli", 51: "carrot", 52: "hot dog", 53: "pizza", 54: "donut",
    55: "cake", 56: "chair", 57: "couch", 58: "potted plant", 59: "bed",
    60: "dining table", 61: "toilet", 62: "tv", 63: "laptop", 64: "mouse",
    65: "remote", 66: "keyboard", 67: "cell phone", 68: "microwave", 69: "oven",
    70: "toaster", 71: "sink", 72: "refrigerator", 73: "book", 74: "clock",
    75: "vase", 76: "scissors", 77: "teddy bear", 78: "hair drier", 79: "toothbrush",
}


class RFDETRAdapter(IDetector):
    """Adapter for Roboflow RF-DETR object detection models."""

    SUPPORTED_VARIANTS = ("nano", "small", "medium", "large")

    def __init__(self) -> None:
        self.model = None
        self.weights: Optional[str] = None
        self.variant: str = "small"
        self.confidence_threshold: float = 0.35
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
        self.confidence_threshold = float(kwargs.get("confidence", kwargs.get("conf", 0.35)))
        self.device = str(kwargs.get("device", "cpu")).lower()
        self.variant = str(kwargs.get("variant", kwargs.get("model_variant", "small"))).lower()
        self.classes_list = kwargs.get("classes_list", None)
        self.backend = str(kwargs.get("backend", "pytorch")).lower()

        insz = kwargs.get("input_size", (640, 640))
        if isinstance(insz, int):
            self.input_size = (insz, insz)
        elif isinstance(insz, (list, tuple)) and len(insz) == 2:
            self.input_size = (int(insz[0]), int(insz[1]))

        # Handle ONNX weights directly if requested or format is .onnx
        ext = Path(weights).suffix.lower() if weights else ""
        if ext == ".onnx" or self.backend in ("onnx", "onnxruntime"):
            self._load_onnx(weights)
            return

        # Attempt to load PyTorch RF-DETR model via `rfdetr` package
        try:
            import rfdetr
        except ImportError:
            raise ModelLoadingError(
                "RF-DETR backend requires the 'rfdetr' package. "
                "Install it using: pip install rfdetr (or pip install -r requirements-rfdetr.txt). "
                "Alternatively, you can export your model to ONNX format to run via ONNX Runtime."
            )

        model_cls_map = {
            "nano": getattr(rfdetr, "RFDETRNano", None),
            "small": getattr(rfdetr, "RFDETRSmall", None),
            "medium": getattr(rfdetr, "RFDETRMedium", None),
            "large": getattr(rfdetr, "RFDETRLarge", None),
        }
        model_cls = model_cls_map.get(self.variant)
        if model_cls is None:
            model_cls = getattr(rfdetr, "RFDETRSmall", None) or getattr(rfdetr, "RFDETRMedium", None)

        if model_cls is None:
            raise ModelLoadingError(f"RF-DETR variant '{self.variant}' is not available in the installed rfdetr package.")

        try:
            # Check if weights is a valid existing path or if downloading default pretrained
            if weights and Path(weights).is_file():
                self.model = model_cls(pretrain_weights=str(weights))
            else:
                self.model = model_cls()

            # Attempt to retrieve classes if model embeds them
            if hasattr(self.model, "classes") and self.model.classes:
                if isinstance(self.model.classes, (list, tuple)):
                    self.classes_map = {i: name for i, name in enumerate(self.model.classes)}
                elif isinstance(self.model.classes, dict):
                    self.classes_map = {int(k): str(v) for k, v in self.model.classes.items()}
        except Exception as e:
            raise ModelLoadingError(f"Failed to initialize RF-DETR model from '{weights}': {e}") from e

    def _load_onnx(self, weights_path: str) -> None:
        from system.inference.onnx_backend import ONNXBackend
        backend = ONNXBackend(device=self.device)
        backend.load(weights_path)
        self._onnx_session = backend
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
            architecture="rf_detr",
            model_name=Path(self.weights).stem if self.weights else f"rf-detr-{self.variant}",
            model_variant=self.variant,
            version="1.11.0",
            weights_path=self.weights,
            device=self.device,
            inference_backend=self.backend,
            num_classes=len(self.classes_map),
            classes=self.classes_map,
            input_size=self.input_size,
            parameters={
                'confidence': self.confidence_threshold,
                'variant': self.variant,
                'license': 'Apache 2.0 (Core Models)',
            },
        )

    def predict(self, image: np.ndarray, **kwargs) -> DetectionFrameResult:
        if not self.is_loaded():
            raise ModelNotFoundError("RF-DETR model is not loaded")

        h, w = image.shape[:2]
        t0 = time.perf_counter()
        conf_thresh = float(kwargs.get("confidence", kwargs.get("conf", self.confidence_threshold)))

        detections: list[Detection] = []

        if self._onnx_session is not None:
            # Process via ONNX Runtime
            from system.object_detection.utils import create_blob, parse_detr_outputs
            blob = create_blob(image, self.input_size, {"resize": "letterbox"})
            outputs = self._onnx_session.predict(blob)
            boxes, confs, clss = parse_detr_outputs(
                outputs,
                confidence=conf_thresh,
                input_size=self.input_size,
                image_shape=(h, w),
                classes_list=self.classes_list,
                num_classes=len(self.classes_map),
                output_names=self._onnx_session._output_names,
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
            # Process via PyTorch rfdetr model
            results = self.model.predict(image, threshold=conf_thresh)
            # results is supervision.Detections
            if hasattr(results, "xyxy") and results.xyxy is not None and len(results.xyxy) > 0:
                xyxy = results.xyxy
                confidences = results.confidence
                class_ids = results.class_id
                custom_names = results.data.get("class_name") if hasattr(results, "data") and isinstance(results.data, dict) else None

                for i in range(len(xyxy)):
                    cid = int(class_ids[i])
                    if self.classes_list is not None and cid not in self.classes_list:
                        continue
                    if custom_names is not None and i < len(custom_names):
                        cname = str(custom_names[i])
                    else:
                        cname = self.classes_map.get(cid, f"class_{cid}")

                    box = xyxy[i]
                    detections.append(
                        Detection(
                            class_id=cid,
                            class_name=cname,
                            confidence=float(confidences[i]),
                            x1=float(box[0]),
                            y1=float(box[1]),
                            x2=float(box[2]),
                            y2=float(box[3]),
                        )
                    )

        duration = time.perf_counter() - t0

        result = DetectionFrameResult(
            detections=detections,
            model_name=Path(self.weights).stem if self.weights else f"rf-detr-{self.variant}",
            model_version="1.11.0",
            inference_backend=self.backend,
            inference_time=duration,
            image_width=w,
            image_height=h,
        )
        result.clip_to_image()
        # Suppress DETR duplicates if needed
        result.suppress_duplicates(iou_threshold=0.6)
        return result

    def export_onnx(self, output_path: str, input_size: Optional[tuple[int, int]] = None) -> str:
        """Export loaded RF-DETR model to ONNX format."""
        if self.model is None:
            raise RuntimeError("Cannot export: RF-DETR PyTorch model is not loaded")

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        sz = input_size or self.input_size

        if hasattr(self.model, "export"):
            self.model.export(str(out), format="onnx", imgsz=sz[0])
            return str(out)

        # PyTorch direct export
        import torch
        dummy_input = torch.randn(1, 3, sz[1], sz[0], device=self.device)
        raw_model = getattr(self.model, "model", self.model)
        raw_model.eval()
        torch.onnx.export(
            raw_model,
            dummy_input,
            str(out),
            input_names=["images"],
            output_names=["boxes", "scores"],
            opset_version=17,
            dynamic_axes={"images": {0: "batch"}, "boxes": {0: "batch"}, "scores": {0: "batch"}},
        )
        return str(out)
