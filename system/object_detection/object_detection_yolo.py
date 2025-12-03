# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 26.12.2024
# Updated: 03.12.2025
# Website: https://bespredel.name

from ultralytics import YOLO, settings

from system.utils.exception_handler import ModelLoadingError, ModelNotFoundError
from system.object_detection.base_object_detection import BaseObjectDetectionService


class ObjectDetectionYOLO(BaseObjectDetectionService):
    def __init__(self) -> None:
        super().__init__()
        self.model = None
        self.confidence = None
        self.iou = None
        self.device = None
        self.vid_stride = None
        self.classes_list = None

        # Disable analytics and crash reporting
        settings.update({'sync': False})

    def detect(self, image, **kwargs):
        """
        Detects objects in an image using a pre-trained model.

        Args:
            image: The input image as a numpy array.

        Returns:
            tuple: (boxes_xyxy, confidences, classes)

        Notes:
            - boxes_xyxy: ndarray with shape (N, 4)
            - confidences: ndarray with shape (N,)
            - classes: ndarray with shape (N,), integer class IDs
        """

        if self.model is None:
            raise ModelNotFoundError('Model is not loaded')

        results = self.model.predict(
            image,
            conf=self.confidence,
            iou=self.iou,
            device=self.device,
            vid_stride=self.vid_stride,
            classes=self.classes_list,
            # half=True
        )

        boxes = results[0].boxes
        boxes_xyxy = boxes.xyxy.cpu().numpy()
        confidences = boxes.conf.cpu().numpy()
        classes = boxes.cls.cpu().numpy().astype(int)

        return boxes_xyxy, confidences, classes

    def load_model(self, weights: str, **kwargs):
        """
        Loads a pre-trained model for object detection.

        Args:
            weights (str): The path to the pre-trained model weights file.
            **kwargs: Additional keyword arguments.

        Returns:
            None
        """

        if not weights:
            raise ModelNotFoundError('Model is not found')

        # Configuration model
        self.confidence = kwargs.get('confidence', 0.5)
        self.iou = kwargs.get('iou', 0.7)
        self.device = kwargs.get('device', 'cpu')
        self.vid_stride = kwargs.get('vid_stride', 1)
        self.classes_list = kwargs.get('classes_list', None)

        try:
            self.model = YOLO(weights)
        except Exception as e:
            raise ModelLoadingError(f"Error loading model: {e}")
