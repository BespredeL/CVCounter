# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 26.12.2024
# Updated: 26.12.2024
# Website: https://bespredel.name

import numpy as np
from ultralytics import YOLO, settings

from system.exception_handler import ModelLoadingError, ModelNotFoundError
from system.base_object_detection import BaseObjectDetectionService


class ObjectDetection(BaseObjectDetectionService):
    def __init__(self) -> None:
        super().__init__()
        self.model = None

        # Disable analytics and crash reporting
        settings.update({'sync': False})

    def detect(self, image: np.ndarray, confidence: float, iou: float, device: str, vid_stride: int, classes_list: list):
        if self.model is None:
            raise ModelNotFoundError('Model is not loaded')

        results = self.model.predict(
            image,
            conf=confidence,
            iou=iou,
            device=device,
            vid_stride=vid_stride,
            classes=classes_list
        )

        return results[0].boxes.xyxy.cpu().numpy(), results[0].boxes.conf.cpu().numpy()

    def load_model(self, weights: str):
        if not weights:
            raise ModelNotFoundError('Model is not found')

        try:
            self.model = YOLO(weights)
        except Exception as e:
            raise ModelLoadingError(f"Error loading model: {e}")
