# -*- coding: utf-8 -*-
# ! python3

"""
D-FINE (Distribution Refinement DETR) Adapter for CVCounter.
Provides integration with Peterande/D-FINE real-time object detection
for PyTorch (CUDA/CPU) and ONNX Runtime inference.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np

from system.detection.interface import IDetector, ModelInfo
from system.detection.result import Detection, DetectionFrameResult
from system.detection.adapters.rf_detr_adapter import COCO_CLASSES_80
from system.utils.exception_handler import ModelLoadingError, ModelNotFoundError


class DFINEAdapter(IDetector):
    """Adapter for D-FINE object detection models."""

    SUPPORTED_VARIANTS = ("nano", "small", "medium", "large", "xlarge")

    def __init__(self) -> None:
        self.model = None
        self.weights: Optional[str] = None
        self.variant: str = "small"
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
        self.confidence_threshold = float(kwargs.get("confidence", kwargs.get("conf", 0.4)))
        self.device = str(kwargs.get("device", "cpu")).lower()
        self.variant = str(kwargs.get("variant", kwargs.get("model_variant", "small"))).lower()
        self.classes_list = kwargs.get("classes_list", None)
        self.backend = str(kwargs.get("backend", "pytorch")).lower()

        insz = kwargs.get("input_size", (640, 640))
        if isinstance(insz, int):
            self.input_size = (insz, insz)
        elif isinstance(insz, (list, tuple)) and len(insz) == 2:
            self.input_size = (int(insz[0]), int(insz[1]))

        # Handle custom classes if supplied
        if "classes" in kwargs and isinstance(kwargs["classes"], dict):
            self.classes_map = {int(k): str(v) for k, v in kwargs["classes"].items()}

        ext = Path(weights).suffix.lower() if weights else ""
        if ext == ".onnx" or self.backend in ("onnx", "onnxruntime"):
            self._load_onnx(weights)
            return

        # Attempt to load PyTorch D-FINE checkpoint
        try:
            import torch
        except ImportError:
            raise ModelLoadingError("PyTorch is required for D-FINE PyTorch inference.")

        if not weights or not Path(weights).is_file():
            raise ModelNotFoundError(f"D-FINE weights file not found: {weights}")

        try:
            device_obj = torch.device(self.device if torch.cuda.is_available() and "cuda" in self.device else "cpu")
            checkpoint = torch.load(weights, map_location=device_obj, weights_only=False)

            # Check if checkpoint contains full model or state_dict
            if isinstance(checkpoint, torch.nn.Module):
                self.model = checkpoint
            elif isinstance(checkpoint, dict):
                # Standard D-FINE / DETR checkpoint dict
                if "model" in checkpoint and isinstance(checkpoint["model"], torch.nn.Module):
                    self.model = checkpoint["model"]
                elif "ema" in checkpoint and isinstance(checkpoint["ema"], dict) and "module" in checkpoint["ema"]:
                    self.model = checkpoint["ema"]["module"]
                else:
                    # Save state_dict directly or wrap
                    self.model = checkpoint.get("model_state_dict") or checkpoint.get("state_dict") or checkpoint

            if hasattr(self.model, "eval"):
                self.model.eval()
                if "cuda" in self.device and torch.cuda.is_available():
                    self.model.to(self.device)
        except Exception as e:
            raise ModelLoadingError(f"Failed to load D-FINE checkpoint from '{weights}': {e}") from e

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
            architecture="d_fine",
            model_name=Path(self.weights).stem if self.weights else f"dfine_{self.variant}",
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
                'author': 'Peterande/D-FINE',
                'license': 'Apache 2.0',
            },
        )

    def predict(self, image: np.ndarray, **kwargs) -> DetectionFrameResult:
        if not self.is_loaded():
            raise ModelNotFoundError("D-FINE model is not loaded")

        h, w = image.shape[:2]
        t0 = time.perf_counter()
        conf_thresh = float(kwargs.get("confidence", kwargs.get("conf", self.confidence_threshold)))

        detections: list[Detection] = []

        if self._onnx_session is not None:
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
            # PyTorch inference
            import torch
            import cv2
            device_obj = torch.device(self.device if torch.cuda.is_available() and "cuda" in self.device else "cpu")

            # Preprocessing: resize to self.input_size, BGR to RGB, normalize [0, 1]
            in_w, in_h = self.input_size
            resized = cv2.resize(image, (in_w, in_h))
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            img_tensor = torch.from_numpy(rgb).permute(2, 0, 1).float().div(255.0).unsqueeze(0).to(device_obj)

            with torch.no_grad():
                if callable(self.model):
                    preds = self.model(img_tensor)
                else:
                    preds = None

            if preds is not None:
                # Postprocess D-FINE / DETR output: (boxes, scores)
                boxes_tensor = None
                scores_tensor = None
                if isinstance(preds, (tuple, list)) and len(preds) >= 2:
                    boxes_tensor, scores_tensor = preds[0], preds[1]
                elif isinstance(preds, dict):
                    boxes_tensor = preds.get("pred_boxes")
                    scores_tensor = preds.get("pred_logits")

                if boxes_tensor is not None and scores_tensor is not None:
                    boxes_np = boxes_tensor.squeeze(0).cpu().numpy()
                    scores_np = scores_tensor.squeeze(0).cpu().numpy()

                    # Apply sigmoid to logits if scores are unnormalized logits
                    if np.min(scores_np) < 0.0 or np.max(scores_np) > 1.0:
                        scores_np = 1.0 / (1.0 + np.exp(-scores_np))

                    for i in range(len(boxes_np)):
                        class_id = int(np.argmax(scores_np[i]))
                        conf = float(scores_np[i][class_id])
                        if conf < conf_thresh:
                            continue
                        if self.classes_list is not None and class_id not in self.classes_list:
                            continue

                        box = boxes_np[i]
                        # If coordinates are normalized [cx, cy, w, h]
                        if np.max(box) <= 1.0:
                            cx, cy, bw, bh = box[0] * w, box[1] * h, box[2] * w, box[3] * h
                            x1 = cx - bw / 2.0
                            y1 = cy - bh / 2.0
                            x2 = cx + bw / 2.0
                            y2 = cy + bh / 2.0
                        else:
                            # Coordinates in input_size or image scale
                            scale_x = w / in_w
                            scale_y = h / in_h
                            x1 = box[0] * scale_x
                            y1 = box[1] * scale_y
                            x2 = box[2] * scale_x
                            y2 = box[3] * scale_y

                        cname = self.classes_map.get(class_id, f"class_{class_id}")
                        detections.append(
                            Detection(
                                class_id=class_id,
                                class_name=cname,
                                confidence=conf,
                                x1=float(x1),
                                y1=float(y1),
                                x2=float(x2),
                                y2=float(y2),
                            )
                        )

        duration = time.perf_counter() - t0

        result = DetectionFrameResult(
            detections=detections,
            model_name=Path(self.weights).stem if self.weights else f"dfine_{self.variant}",
            model_version="1.0.0",
            inference_backend=self.backend,
            inference_time=duration,
            image_width=w,
            image_height=h,
        )
        result.clip_to_image()
        result.suppress_duplicates(iou_threshold=0.6)
        return result

    def export_onnx(self, output_path: str, input_size: Optional[tuple[int, int]] = None) -> str:
        """Export loaded D-FINE PyTorch model to ONNX."""
        if self.model is None or not hasattr(self.model, "eval"):
            raise RuntimeError("Cannot export: D-FINE PyTorch model is not loaded")

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        sz = input_size or self.input_size

        import torch
        dummy_input = torch.randn(1, 3, sz[1], sz[0], device=self.device)
        self.model.eval()
        torch.onnx.export(
            self.model,
            dummy_input,
            str(out),
            input_names=["images"],
            output_names=["boxes", "scores"],
            opset_version=17,
            dynamic_axes={"images": {0: "batch"}, "boxes": {0: "batch"}, "scores": {0: "batch"}},
        )
        return str(out)
