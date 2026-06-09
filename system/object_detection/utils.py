# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 20.05.2026
# Updated: 09.06.2026
# Website: https://bespredel.name

from typing import Iterable, Optional, Sequence, Tuple

import cv2
import numpy as np
from numpy import ndarray

DetectionResult = Tuple[ndarray, ndarray, ndarray]


def normalize_input_size(input_size: int | Sequence[int]) -> Tuple[int, int]:
    """
    Normalize the input size.

    Args:
        input_size (int | Sequence[int]): The input size to normalize.

    Returns:
        Tuple[int, int]: The normalized input size.
    """
    if isinstance(input_size, (list, tuple)):
        if len(input_size) != 2:
            raise ValueError("'input_size' must be an int or a pair [width, height]")
        return int(input_size[0]), int(input_size[1])
    size = int(input_size)
    return size, size


def filter_by_classes(
        boxes_xyxy: ndarray,
        confidences: ndarray,
        classes: ndarray,
        classes_list: Optional[Iterable[int]],
) -> DetectionResult:
    """
    Filter boxes by classes.

    Args:
        boxes_xyxy (ndarray): The boxes to filter.
        confidences (ndarray): The confidences to filter.
        classes (ndarray): The classes to filter.
        classes_list (Optional[Iterable[int]]): The classes list to filter by.

    Returns:
        DetectionResult: The filtered boxes, confidences and classes.
    """
    if not classes_list:
        return boxes_xyxy, confidences, classes

    allowed = {int(class_id) for class_id in classes_list}
    mask = np.isin(classes, list(allowed))
    return boxes_xyxy[mask], confidences[mask], classes[mask]


def nms_boxes(
        boxes_xyxy: ndarray,
        confidences: ndarray,
        classes: ndarray,
        iou_threshold: float,
) -> DetectionResult:
    """
    Non-maximum suppression for boxes.

    Args:
        boxes_xyxy (ndarray): The boxes to suppress.
        confidences (ndarray): The confidences to suppress.
        classes (ndarray): The classes to suppress.
        iou_threshold (float): The IoU threshold to suppress by.

    Returns:
        DetectionResult: The suppressed boxes, confidences and classes.
    """
    if len(boxes_xyxy) == 0:
        return boxes_xyxy, confidences, classes

    keep_indices = []
    for class_id in np.unique(classes):
        class_mask = classes == class_id
        class_boxes = boxes_xyxy[class_mask]
        class_scores = confidences[class_mask]
        class_indices = np.where(class_mask)[0]

        order = class_scores.argsort()[::-1]
        while order.size > 0:
            current = order[0]
            keep_indices.append(class_indices[current])
            if order.size == 1:
                break

            current_box = class_boxes[current]
            remaining_boxes = class_boxes[order[1:]]
            ious = _box_iou(current_box, remaining_boxes)
            order = order[1:][ious <= iou_threshold]

    keep_indices = np.array(keep_indices, dtype=int)
    return boxes_xyxy[keep_indices], confidences[keep_indices], classes[keep_indices]


def _box_iou(box: ndarray, boxes: ndarray) -> ndarray:
    """
    Calculate the IoU for a box and a list of boxes.

    Args:
        box (ndarray): The box to calculate the IoU for.
        boxes (ndarray): The list of boxes to calculate the IoU for.

    Returns:
        ndarray: The IoU for the box and the list of boxes.
    """
    x1 = np.maximum(box[0], boxes[:, 0])
    y1 = np.maximum(box[1], boxes[:, 1])
    x2 = np.minimum(box[2], boxes[:, 2])
    y2 = np.minimum(box[3], boxes[:, 3])

    intersection = np.maximum(0.0, x2 - x1) * np.maximum(0.0, y2 - y1)
    box_area = (box[2] - box[0]) * (box[3] - box[1])
    boxes_area = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    union = box_area + boxes_area - intersection + 1e-6
    return intersection / union


def parse_yolo_outputs(
        outputs: list[ndarray] | ndarray,
        confidence: float,
        iou: float,
        input_size: Tuple[int, int],
        image_shape: Tuple[int, int, int],
        classes_list: Optional[Iterable[int]] = None,
) -> DetectionResult:
    """
    Parse YOLO-style ONNX/OpenCV outputs into xyxy boxes, scores and class IDs.
    Supports YOLOv5/v8 ONNX layouts.

    Args:
        outputs (list[ndarray] | ndarray): The outputs to parse.
        confidence (float): The confidence threshold to parse by.
        iou (float): The IoU threshold to parse by.
        input_size (Tuple[int, int]): The input size to parse by.
        image_shape (Tuple[int, int, int]): The image shape to parse by.
        classes_list (Optional[Iterable[int]]): The classes list to parse by.

    Returns:
        DetectionResult: The parsed boxes, confidences and classes.
    """
    if isinstance(outputs, list):
        if len(outputs) == 1:
            prediction = outputs[0]
        else:
            prediction = np.concatenate([output.reshape(output.shape[0], -1) for output in outputs], axis=2)
    else:
        prediction = outputs

    prediction = np.squeeze(prediction)
    if prediction.ndim == 3:
        prediction = prediction[0]

    if prediction.shape[0] in (4, 5, 84, 85) and prediction.shape[0] < prediction.shape[1]:
        prediction = prediction.transpose(1, 0)

    if prediction.shape[-1] >= 6 and prediction.shape[0] <= 1000:
        boxes_xyxy = prediction[:, :4].astype(np.float32)
        confidences = prediction[:, 4].astype(np.float32)
        classes = prediction[:, 5].astype(np.int32)
    else:
        boxes_xyxy, confidences, classes = _parse_yolo_matrix(prediction, confidence)

    boxes_xyxy = _scale_boxes_to_image(boxes_xyxy, input_size, image_shape)

    mask = confidences >= confidence
    boxes_xyxy = boxes_xyxy[mask]
    confidences = confidences[mask]
    classes = classes[mask]

    boxes_xyxy, confidences, classes = nms_boxes(boxes_xyxy, confidences, classes, iou)
    return filter_by_classes(boxes_xyxy, confidences, classes, classes_list)


def _parse_yolo_matrix(prediction: ndarray, confidence: float) -> Tuple[ndarray, ndarray, ndarray]:
    """
    Parse a YOLO matrix.

    Args:
        prediction (ndarray): The prediction to parse.
        confidence (float): The confidence threshold to parse by.

    Returns:
        Tuple[ndarray, ndarray, ndarray]: The parsed boxes, confidences and classes.
    """
    if prediction.shape[-1] == 6:
        boxes = prediction[:, :4]
        confidences = prediction[:, 4]
        classes = prediction[:, 5].astype(np.int32)
        return boxes, confidences, classes

    class_scores = prediction[:, 4:]
    classes = np.argmax(class_scores, axis=1).astype(np.int32)
    confidences = class_scores[np.arange(len(class_scores)), classes]

    boxes = prediction[:, :4]
    if np.max(boxes[:, 2:4]) <= 2.0:
        boxes_xyxy = _xywh_to_xyxy(boxes)
    else:
        boxes_xyxy = boxes.astype(np.float32)

    pre_mask = confidences >= confidence
    return boxes_xyxy[pre_mask], confidences[pre_mask], classes[pre_mask]


def _xywh_to_xyxy(boxes: ndarray) -> ndarray:
    """
    Convert YOLO-style boxes to xyxy format.

    Args:
        boxes (ndarray): The boxes to convert.

    Returns:
        ndarray: The converted boxes.
    """
    center_x, center_y, width, height = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    x1 = center_x - width / 2
    y1 = center_y - height / 2
    x2 = center_x + width / 2
    y2 = center_y + height / 2
    return np.stack([x1, y1, x2, y2], axis=1).astype(np.float32)


def _scale_boxes_to_image(
        boxes_xyxy: ndarray,
        input_size: Tuple[int, int],
        image_shape: Tuple[int, int, int],
) -> ndarray:
    """
    Scale boxes to the image size.

    Args:
        boxes_xyxy (ndarray): The boxes to scale.
        input_size (Tuple[int, int]): The input size to scale by.
        image_shape (Tuple[int, int, int]): The image shape to scale by.

    Returns:
        ndarray: The scaled boxes.
    """
    if len(boxes_xyxy) == 0:
        return boxes_xyxy

    image_height, image_width = image_shape[:2]
    input_width, input_height = input_size
    gain = min(input_width / image_width, input_height / image_height)
    pad_x = (input_width - image_width * gain) / 2
    pad_y = (input_height - image_height * gain) / 2

    boxes = boxes_xyxy.copy()
    boxes[:, [0, 2]] = (boxes[:, [0, 2]] - pad_x) / gain
    boxes[:, [1, 3]] = (boxes[:, [1, 3]] - pad_y) / gain

    boxes[:, [0, 2]] = np.clip(boxes[:, [0, 2]], 0, image_width)
    boxes[:, [1, 3]] = np.clip(boxes[:, [1, 3]], 0, image_height)
    return boxes


def create_blob(image: ndarray, input_size: Tuple[int, int]) -> ndarray:
    """
    Create a blob from an image.

    Args:
        image (ndarray): The image to create a blob from.
        input_size (Tuple[int, int]): The input size to create a blob by.

    Returns:
        ndarray: The created blob.
    """
    return cv2.dnn.blobFromImage(
        image,
        scalefactor=1 / 255.0,
        size=input_size,
        mean=(0, 0, 0),
        swapRB=True,
        crop=False,
    )
