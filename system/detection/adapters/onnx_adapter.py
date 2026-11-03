# -*- coding: utf-8 -*-
# ! python3

"""
Generic ONNX Runtime Detector Adapter for CVCounter.
Provides standalone IDetector implementation over ONNX models with dynamic
execution provider fallback and automatic output parsing.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import numpy as np
from numpy import ndarray

from system.detection.backends.onnx import ONNXSession
from system.detection.exceptions import ModelLoadingError, ModelNotFoundError
from system.detection.interface import IDetector, ModelInfo
from system.detection.metadata import extract_model_classes, load_model_manifest
from system.detection.postprocessing import parse_detr_outputs, parse_yolo_outputs
from system.detection.result import Detection, DetectionFrameResult
from system.detection.transforms import create_blob, normalize_input_size, preprocessing_from_manifest


class GenericONNXAdapter(IDetector):
    """
    Standalone adapter for ONNX models using ONNXSession.
    Supports YOLOv5-YOLO26, RT-DETR, and custom ONNX models via manifests.
    """

    def __init__(self) -> None:
        self.session = ONNXSession()
        self.weights_path: Optional[str] = None
        self.device: str = "cpu"
        self.confidence: float = 0.5
        self.iou: float = 0.7
        self.input_size: tuple[int, int] = (640, 640)
        self.classes_list: Optional[List[int]] = None
        self.classes_map: Dict[int, str] = {}
        self.decoder: str = "yolo_outputs"
        self.box_format: str = "auto"
        self.box_coordinates: str = "auto"
        self.score_activation: str = "auto"
        self.is_end2end: Optional[bool] = None
        self.preprocessing: dict[str, Any] = {}
        self.manifest: Optional[Any] = None

    def is_loaded(self) -> bool:
        """Check if ONNX session is loaded."""
        return self.session.is_loaded

    def model_info(self) -> ModelInfo:
        """Return standardized runtime model metadata."""
        path_obj = Path(self.weights_path) if self.weights_path else None
        model_name = path_obj.stem if path_obj else "onnx"

        return ModelInfo(
            architecture="onnx",
            model_name=model_name,
            model_variant="onnx",
            weights_path=self.weights_path,
            device=self.device,
            active_provider=self.session.active_provider or "CPUExecutionProvider",
            inference_backend="onnxruntime",
            num_classes=len(self.classes_map),
            classes=dict(self.classes_map),
            input_size=self.input_size,
            confidence=self.confidence,
            iou=self.iou,
            is_loaded=self.is_loaded(),
        )

    def load_model(self, weights: Union[str, Path], **kwargs: Any) -> None:
        """
        Load an ONNX model, inspect its inputs/outputs, and parse contracts.
        """
        path = Path(weights)
        if not path.is_file():
            raise ModelNotFoundError(f"ONNX weights file not found: {weights}")

        self.weights_path = str(path)
        self.confidence = float(kwargs.get("confidence", kwargs.get("conf", self.confidence)))
        self.iou = float(kwargs.get("iou", self.iou))
        self.device = str(kwargs.get("device", self.device)).lower()
        self.classes_list = kwargs.get("classes_list", None)

        # Input size
        if "input_size" in kwargs:
            self.input_size = normalize_input_size(kwargs["input_size"])

        # Sidecar manifest
        self.manifest = load_model_manifest(self.weights_path)
        self.preprocessing = preprocessing_from_manifest(self.manifest)

        if self.manifest is not None:
            if self.manifest.decoder not in ("yolo_outputs", "detr_outputs", "end2end"):
                raise ModelLoadingError(
                    f"Decoder '{self.manifest.decoder}' is not supported by the ONNX detection adapter"
                )
            self.decoder = self.manifest.decoder
            contract = self.manifest.output_contract or {}
            self.box_format = contract.get("box_format", "auto")
            self.box_coordinates = contract.get("box_coordinates", "auto")
            self.score_activation = contract.get("score_activation", "auto")
            self.is_end2end = contract.get("is_end2end", None)

        # Extract classes
        extracted_classes, _ = extract_model_classes(self.weights_path)
        self.classes_map = extracted_classes

        # Initialize ONNX Session with providers and fallback
        providers = kwargs.get("providers", None)
        self.session.load(self.weights_path, device=self.device, providers=providers)

        # Inspect declared input shape if dynamic
        if self.session.input_shapes:
            inp_shape = self.session.input_shapes[0]
            if len(inp_shape) == 4 and isinstance(inp_shape[2], int) and isinstance(inp_shape[3], int):
                if "input_size" not in kwargs:
                    self.input_size = (inp_shape[3], inp_shape[2])

    def unload(self) -> None:
        """Release session resources."""
        self.session.unload()
        self.weights_path = None
        self.classes_map.clear()
        self.manifest = None

    def detect(self, image: ndarray, **kwargs: Any) -> DetectionFrameResult:
        """
        Run inference on frame through ONNXSession and parse outputs.
        """
        if not self.session.is_loaded:
            raise ModelNotFoundError("ONNX model is not loaded")

        conf = float(kwargs.get("confidence", kwargs.get("conf", self.confidence)))
        iou = float(kwargs.get("iou", self.iou))
        classes = kwargs.get("classes_list", self.classes_list)

        h, w = image.shape[:2]
        blob = create_blob(image, self.input_size, self.preprocessing)

        start_time = time.perf_counter()
        raw_outputs = self.session.run(blob)
        inference_time = time.perf_counter() - start_time

        resize_mode = str(self.preprocessing.get("resize", "letterbox"))

        if self.decoder == "detr_outputs":
            boxes_xyxy, confidences, class_ids = parse_detr_outputs(
                raw_outputs,
                confidence=conf,
                input_size=self.input_size,
                image_shape=image.shape,
                classes_list=classes,
                num_classes=len(self.classes_map) if self.classes_map else None,
                output_names=self.session.output_names,
                box_format=self.box_format,
                box_coordinates=self.box_coordinates,
                score_activation=self.score_activation,
                resize=resize_mode,
            )
        else:
            boxes_xyxy, confidences, class_ids = parse_yolo_outputs(
                raw_outputs,
                confidence=conf,
                iou=iou,
                input_size=self.input_size,
                image_shape=image.shape,
                classes_list=classes,
                is_end2end=self.is_end2end,
                box_format=self.box_format,
                box_coordinates=self.box_coordinates,
                has_objectness=bool(self.preprocessing.get("has_objectness", False)),
                resize=resize_mode,
            )

        detections: List[Detection] = []
        if len(boxes_xyxy) > 0:
            for i in range(len(boxes_xyxy)):
                cid = int(class_ids[i])
                cname = self.classes_map.get(cid, str(cid))
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
            model_name=Path(self.weights_path).stem if self.weights_path else "onnx",
            inference_backend="onnxruntime",
            inference_time=inference_time,
            image_width=w,
            image_height=h,
        )


__all__ = ["GenericONNXAdapter"]
