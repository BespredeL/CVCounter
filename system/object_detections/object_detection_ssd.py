# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 25.01.2025
# Updated: 25.01.2025
# Website: https://bespredel.name

import torch
import numpy as np
from torchvision.models.detection import ssd300_vgg16
from torchvision.transforms import functional as F

from system.exception_handler import ModelLoadingError, ModelNotFoundError
from system.object_detections.base_object_detection import BaseObjectDetectionService


class ObjectDetectionSSD(BaseObjectDetectionService):
    def __init__(self) -> None:
        super().__init__()
        self.model = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

    def detect(self, image: np.ndarray, confidence: float, iou: float, device: str, vid_stride: int,
               classes_list: list):
        """
        Detects objects in an image using a pre-trained SSD model.

        Args:
            image (np.ndarray): The input image as a numpy array.
            confidence (float): The confidence threshold for object detection.
            iou (float): The IoU threshold for object detection.
            device (str): The device to use for inference ('cpu' by default).
            vid_stride (int): The stride for video processing.
            classes_list (list): The classes for object detection.

        Returns:
            tuple: Bounding boxes, confidences, and detected class indices.
        """

        # Set device
        if device:
            self.device = device

        if self.model is None:
            raise ModelNotFoundError("Model is not loaded")

        image_tensor = F.to_tensor(image).unsqueeze(0).to(self.device)

        self.model = self.model.to(self.device)
        self.model.eval()

        with torch.no_grad():
            results = self.model(image_tensor)[0]

        boxes = results["boxes"].cpu().numpy()
        scores = results["scores"].cpu().numpy()

        mask = scores >= confidence
        boxes = boxes[mask]
        scores = scores[mask]

        return boxes, scores

    def load_model(self, weights: str = None):
        """
        Loads the SSD model for object detection.

        Args:
            weights (str): The path to the model weights file.

        Returns:
            None
        """

        try:
            self.model = ssd300_vgg16(pretrained=True).to(self.device)
        except Exception as e:
            raise ModelLoadingError(f"Error loading model: {e}")
