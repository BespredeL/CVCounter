# -*- coding: utf-8 -*-
# ! python3

"""Legacy alias module. Use system.detection.adapters.yolo_adapter instead."""

from system.detection.adapters.yolo_adapter import UltralyticsYOLOAdapter, YOLOAdapter

__all__ = ["UltralyticsYOLOAdapter", "YOLOAdapter"]
