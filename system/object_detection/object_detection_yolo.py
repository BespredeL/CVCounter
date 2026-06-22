# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 26.12.2024
# Updated: 09.06.2026
# Website: https://bespredel.name

import gc

import torch
from numpy import ndarray
from ultralytics import YOLO, settings
from system.object_detection.base_object_detection import BaseObjectDetectionService, DetectionResult
from system.object_detection.registry import register
from system.utils.exception_handler import ModelLoadingError, ModelNotFoundError
from system.utils.utils import pr_color


@register('yolo')
class ObjectDetectionYOLO(BaseObjectDetectionService):
    def __init__(self) -> None:
        self.model = None
        self.confidence = 0.5
        self.iou = 0.7
        self.device = 'cpu'
        self.vid_stride = 1
        self.classes_list = None
        self.verbose = False

        settings.update({'sync': False})

    def detect(self, image: ndarray, **kwargs) -> DetectionResult:
        if self.model is None:
            raise ModelNotFoundError('Model is not loaded')

        results = self.model.predict(
            image,
            conf=self.confidence,
            iou=self.iou,
            device=self.device,
            vid_stride=self.vid_stride,
            classes=self.classes_list,
            verbose=kwargs.get('verbose', self.verbose),
        )

        boxes = results[0].boxes
        boxes_xyxy = boxes.xyxy.cpu().numpy()
        confidences = boxes.conf.cpu().numpy()
        classes = boxes.cls.cpu().numpy().astype(int)

        return boxes_xyxy, confidences, classes

    def load_model(self, weights: str, **kwargs) -> None:
        if not weights:
            raise ModelNotFoundError('Model is not found')

        self.confidence = kwargs.get('confidence', 0.5)
        self.iou = kwargs.get('iou', 0.7)
        self.device = kwargs.get('device', 'cpu')
        self.vid_stride = kwargs.get('vid_stride', 1)
        self.classes_list = kwargs.get('classes_list', None)
        self.verbose = bool(kwargs.get('verbose', kwargs.get('debug', False)))

        try:
            self.model = YOLO(weights)
        except Exception as e:
            raise ModelLoadingError(f"Error loading model: {e}")

    def cleanup(self) -> None:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            gc.collect()
            pr_color("Context cleared", 'green')
