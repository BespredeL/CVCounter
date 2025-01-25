# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 26.12.2024
# Updated: 27.12.2024
# Website: https://bespredel.name

import torch
import numpy as np

from system.exception_handler import ModelLoadingError, ModelNotFoundError
from system.object_detections.base_object_detection import BaseObjectDetectionService


class ObjectDetectionYOLOv7(BaseObjectDetectionService):
    def __init__(self) -> None:
        super().__init__()
        self.model = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

    def detect(self, image: np.ndarray, confidence: float, iou: float, device: str, vid_stride: int,
               classes_list: list):
        """
        Detects objects in an image using a pre-trained YOLOv7 model.

        Args:
            image (np.ndarray): The input image as a numpy array.
            confidence (float): The confidence threshold for object detection.
            iou (float): The IoU threshold for object detection.
            device (str): The device to use for inference ('cpu' or 'cuda').
            vid_stride (int): The stride for video processing.
            classes_list (list): The classes for object detection.

        Returns:
            ndarray: An array of updated results after tracking the detected objects.
        """

        if device:
            self.device = device

        if self.model is None:
            raise ModelNotFoundError('Model is not loaded')

        image_tensor = torch.from_numpy(image).float() / 255.0
        image_tensor = image_tensor.permute(2, 0, 1).unsqueeze(0)
        image_tensor = image_tensor.to(device)

        with torch.no_grad():
            results = self.model(image_tensor)

        boxes = results.xyxy[0].cpu().numpy()
        scores = results.conf[0].cpu().numpy()

        mask = scores >= confidence
        boxes = boxes[mask]
        scores = scores[mask]

        return boxes, scores

    def load_model(self, weights: str):
        """
        Loads a pre-trained YOLOv7 model for object detection.

        Args:
            weights (str): The path to the pre-trained model weights file.

        Returns:
            None
        """

        if not weights:
            raise ModelNotFoundError('Model is not found')

        try:
            self.model = torch.hub.load('WongKinYiu/yolov7', 'custom', path=weights, source='github')
            self.model.to(self.device).eval()
        except Exception as e:
            raise ModelLoadingError(f"Error loading model: {e}")
