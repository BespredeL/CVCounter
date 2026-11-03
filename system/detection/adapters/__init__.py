# -*- coding: utf-8 -*-
# ! python3

"""
Adapters for detection models (YOLO, ONNX, RF-DETR, D-FINE, RTMDet).
"""

from system.detection.adapters.yolo_adapter import YOLOAdapter, UltralyticsYOLOAdapter
from system.detection.adapters.onnx_adapter import GenericONNXAdapter
from system.detection.adapters.rf_detr_adapter import RFDETRAdapter
from system.detection.adapters.d_fine_adapter import DFINEAdapter
from system.detection.adapters.rtmdet_adapter import RTMDetAdapter

__all__ = [
    "YOLOAdapter",
    "UltralyticsYOLOAdapter",
    "GenericONNXAdapter",
    "RFDETRAdapter",
    "DFINEAdapter",
    "RTMDetAdapter",
]

