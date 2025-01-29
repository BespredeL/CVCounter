# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 26.12.2024
# Updated: 27.12.2024
# Website: https://bespredel.name

import numpy as np
from ultralytics import YOLO, settings

from system.exception_handler import ModelLoadingError, ModelNotFoundError
from system.object_detections.base_object_detection import BaseObjectDetectionService


class ObjectDetectionYOLO(BaseObjectDetectionService):
    def __init__(self) -> None:
        super().__init__()
        self.model = None

        # Disable analytics and crash reporting
        settings.update({'sync': False})

    def detect(self, image: np.ndarray, confidence: float, iou: float, device: str, vid_stride: int, classes_list: list):
        """
        Detects objects in an image using a pre-trained model.

        Args:
            image (np.ndarray): The input image as a numpy array.
            confidence (float): The confidence threshold for object detection.
            iou (float): The IoU threshold for object detection.
            device (str): The device to use for inference ('cpu' by default).
            vid_stride (int): The stride for video processing.
            classes_list (list): The classes for object detection.

        Returns:
            ndarray: An array of updated results after tracking the detected objects.
        """

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

        boxes_xyxy = results[0].boxes.xyxy.cpu().numpy()
        confidences = results[0].boxes.conf.cpu().numpy()

        return boxes_xyxy, confidences

    def load_model(self, weights: str):
        """
        Loads a pre-trained model for object detection.

        Args:
            weights (str): The path to the pre-trained model weights file.

        Returns:
            None
        """

        if not weights:
            raise ModelNotFoundError('Model is not found')

        try:
            self.model = YOLO(weights)
        except Exception as e:
            raise ModelLoadingError(f"Error loading model: {e}")
