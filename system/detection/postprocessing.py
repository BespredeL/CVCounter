# -*- coding: utf-8 -*-
# ! python3

"""Postprocessing and tensor parsing utilities for object detection models."""

from typing import Iterable, List, Optional, Sequence, Tuple
import cv2
import numpy as np
from numpy import ndarray

# Canonical tuple for detection results prior to DTO wrapping
ParsedDetections = Tuple[ndarray, ndarray, ndarray]  # (boxes_xyxy, confidences, classes)


def filter_by_classes(
    boxes_xyxy: ndarray,
    confidences: ndarray,
    classes: ndarray,
    classes_list: Optional[Iterable[int]] = None,
) -> ParsedDetections:
    """
    Filter detections by an allowed list of class IDs.

    Args:
        boxes_xyxy: Bounding boxes array of shape (N, 4).
        confidences: Confidence scores array of shape (N,).
        classes: Class IDs array of shape (N,).
        classes_list: Optional sequence of integer class IDs to retain.

    Returns:
        ParsedDetections: (filtered_boxes, filtered_confidences, filtered_classes).
    """
    if classes_list is None or len(boxes_xyxy) == 0:
        return boxes_xyxy, confidences, classes

    allowed = set(int(c) for c in classes_list)
    mask = np.isin(classes, list(allowed))
    return boxes_xyxy[mask], confidences[mask], classes[mask]


def box_iou(box: ndarray, boxes: ndarray) -> ndarray:
    """
    Calculate Intersection over Union (IoU) between a single box and an array of boxes.

    Args:
        box: Single bounding box [x1, y1, x2, y2].
        boxes: Array of bounding boxes with shape (N, 4).

    Returns:
        ndarray: 1D array of IoU values.
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


def nms_boxes(
    boxes_xyxy: ndarray,
    confidences: ndarray,
    classes: ndarray,
    iou_threshold: float,
) -> ParsedDetections:
    """
    Non-Maximum Suppression (NMS) for multiclass bounding boxes.

    Args:
        boxes_xyxy: Boxes array of shape (N, 4) in [x1, y1, x2, y2] format.
        confidences: 1D array of confidence scores.
        classes: 1D array of class IDs.
        iou_threshold: IoU overlap threshold for suppression.

    Returns:
        ParsedDetections: (suppressed_boxes, suppressed_confidences, suppressed_classes).
    """
    if len(boxes_xyxy) == 0:
        return boxes_xyxy, confidences, classes

    # Convert [x1, y1, x2, y2] to [x, y, w, h] for cv2.dnn.NMSBoxes
    boxes_xywh = np.empty_like(boxes_xyxy)
    boxes_xywh[:, 0] = boxes_xyxy[:, 0]
    boxes_xywh[:, 1] = boxes_xyxy[:, 1]
    boxes_xywh[:, 2] = np.maximum(0.0, boxes_xyxy[:, 2] - boxes_xyxy[:, 0])
    boxes_xywh[:, 3] = np.maximum(0.0, boxes_xyxy[:, 3] - boxes_xyxy[:, 1])

    # Batched multi-class NMS if supported by OpenCV
    if hasattr(cv2.dnn, 'NMSBoxesBatched'):
        try:
            nms_indices = cv2.dnn.NMSBoxesBatched(
                bboxes=boxes_xywh,
                scores=confidences,
                class_ids=classes.astype(np.int32),
                score_threshold=0.0,
                nms_threshold=float(iou_threshold),
            )
            if len(nms_indices) == 0:
                return (
                    np.empty((0, 4), dtype=boxes_xyxy.dtype),
                    np.empty((0,), dtype=confidences.dtype),
                    np.empty((0,), dtype=classes.dtype),
                )
            keep_indices = np.asarray(nms_indices).flatten()
            return boxes_xyxy[keep_indices], confidences[keep_indices], classes[keep_indices]
        except Exception:
            pass

    keep_indices = []
    # Class-aware NMS loop
    for class_id in np.unique(classes):
        class_mask = classes == class_id
        class_indices = np.where(class_mask)[0]

        cls_boxes = boxes_xywh[class_mask]
        cls_scores = confidences[class_mask]

        nms_indices = cv2.dnn.NMSBoxes(
            bboxes=cls_boxes,
            scores=cls_scores,
            score_threshold=0.0,
            nms_threshold=float(iou_threshold),
        )
        if len(nms_indices) > 0:
            flat_indices = np.asarray(nms_indices).flatten()
            keep_indices.extend(class_indices[flat_indices])

    if not keep_indices:
        return (
            np.empty((0, 4), dtype=boxes_xyxy.dtype),
            np.empty((0,), dtype=confidences.dtype),
            np.empty((0,), dtype=classes.dtype),
        )

    keep_indices = np.array(keep_indices, dtype=int)
    return boxes_xyxy[keep_indices], confidences[keep_indices], classes[keep_indices]


def _xywh_to_xyxy(boxes: ndarray) -> ndarray:
    """Convert [cx, cy, w, h] boxes to [x1, y1, x2, y2]."""
    center_x, center_y, width, height = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    x1 = center_x - width / 2.0
    y1 = center_y - height / 2.0
    x2 = center_x + width / 2.0
    y2 = center_y + height / 2.0
    return np.stack([x1, y1, x2, y2], axis=1).astype(np.float32)


def _looks_like_xyxy(boxes: ndarray) -> bool:
    """Decide whether raw head columns already hold corner coordinates."""
    if len(boxes) == 0:
        return True
    if float(np.max(boxes[:, 2:4])) <= 2.0:
        return False
    ordered = (boxes[:, 2] > boxes[:, 0]) & (boxes[:, 3] > boxes[:, 1])
    return bool(np.mean(ordered) >= 0.95)


def _convert_boxes(boxes: ndarray, box_format: str) -> ndarray:
    """Convert box matrix to xyxy layout according to box_format."""
    if box_format == 'cxcywh':
        return _xywh_to_xyxy(boxes)
    if box_format not in ('xyxy', 'auto'):
        raise ValueError(f"Unsupported detection box format: '{box_format}'")
    if box_format == 'auto' and not _looks_like_xyxy(boxes):
        return _xywh_to_xyxy(boxes)
    return boxes.astype(np.float32)


def scale_boxes_to_image(
    boxes_xyxy: ndarray,
    input_size: Tuple[int, int],
    image_shape: Tuple[int, int, int],
    resize: str = 'letterbox',
) -> ndarray:
    """
    Scale detection bounding boxes from model input canvas back to original image space.

    Args:
        boxes_xyxy: Boxes in input space with shape (N, 4).
        input_size: Model input canvas (width, height).
        image_shape: Original image shape (height, width, channels).
        resize: Resizing mode used during preprocessing ('letterbox' or 'stretch').

    Returns:
        ndarray: Scaled boxes clipped to image boundaries.
    """
    if len(boxes_xyxy) == 0:
        return boxes_xyxy

    image_height, image_width = image_shape[:2]
    boxes = boxes_xyxy.copy()

    # Detect normalized [0..1] coordinates (RT-DETR, RF-DETR)
    if float(np.max(boxes)) <= 1.05:
        boxes[:, [0, 2]] *= image_width
        boxes[:, [1, 3]] *= image_height
    elif resize == 'stretch':
        input_width, input_height = input_size
        boxes[:, [0, 2]] *= image_width / input_width
        boxes[:, [1, 3]] *= image_height / input_height
    else:
        input_width, input_height = input_size
        gain = min(input_width / image_width, input_height / image_height)
        pad_x = (input_width - image_width * gain) / 2.0
        pad_y = (input_height - image_height * gain) / 2.0

        boxes[:, [0, 2]] = (boxes[:, [0, 2]] - pad_x) / gain
        boxes[:, [1, 3]] = (boxes[:, [1, 3]] - pad_y) / gain

    boxes[:, [0, 2]] = np.clip(boxes[:, [0, 2]], 0, image_width)
    boxes[:, [1, 3]] = np.clip(boxes[:, [1, 3]], 0, image_height)
    return boxes


def _merge_outputs(outputs: List[ndarray]) -> ndarray:
    """Concatenate multiple YOLO feature-map tensors along anchor axis."""
    flat: List[ndarray] = []
    for tensor in outputs:
        if tensor.ndim == 4:
            b, c, h, w = tensor.shape
            tensor = tensor.reshape(b, c, h * w)
        flat.append(tensor)
    return np.concatenate(flat, axis=2)


def _parse_yolo_matrix(
    prediction: ndarray,
    confidence: float,
    has_objectness: bool = False,
    box_format: str = 'auto',
) -> ParsedDetections:
    """Parse single-frame prediction matrix into boxes, confidences and class IDs."""
    if prediction.shape[-1] == 6:
        boxes = prediction[:, :4]
        confidences = prediction[:, 4]
        classes = prediction[:, 5].astype(np.int32)
        return _convert_boxes(boxes, box_format), confidences, classes

    matrix = prediction[:, 5:] if has_objectness else prediction[:, 4:]
    classes = np.argmax(matrix, axis=1).astype(np.int32)
    confidences = matrix[np.arange(len(matrix)), classes]
    if has_objectness:
        confidences = confidences * prediction[:, 4]

    boxes = prediction[:, :4]
    boxes_xyxy = _convert_boxes(boxes, 'cxcywh' if has_objectness else box_format)

    pre_mask = confidences >= confidence
    return boxes_xyxy[pre_mask], confidences[pre_mask], classes[pre_mask]


def parse_yolo_outputs(
    outputs: list[ndarray] | ndarray,
    confidence: float,
    iou: float,
    input_size: Tuple[int, int],
    image_shape: Tuple[int, int, int],
    classes_list: Optional[Iterable[int]] = None,
    is_end2end: Optional[bool] = None,
    box_format: str = 'auto',
    box_coordinates: str = 'auto',
    has_objectness: bool = False,
    resize: str = 'letterbox',
) -> ParsedDetections:
    """
    Parse YOLO/RT-DETR-style ONNX outputs into xyxy boxes, scores and class IDs.
    Supports YOLOv5/v8/v9/v10/v11/v12/v26 layouts.

    Args:
        outputs: Runtime tensor output(s).
        confidence: Minimum confidence score threshold.
        iou: IoU threshold for NMS.
        input_size: Model input canvas size (width, height).
        image_shape: Original image shape (height, width, channels).
        classes_list: Optional subset of class IDs to filter.
        is_end2end: If True, skips NMS (for YOLOv10 or models with embedded NMS).
        box_format: Box coordinate layout: 'auto', 'xyxy' or 'cxcywh'.
        box_coordinates: Coordinate space: 'auto', 'normalized' or 'input_pixels'.
        has_objectness: True for heads with column 4 as objectness (YOLOv3-v5).
        resize: Mode used in preprocessing: 'letterbox' or 'stretch'.

    Returns:
        ParsedDetections: (boxes_xyxy, confidences, classes).
    """
    prediction = outputs if isinstance(outputs, ndarray) else _merge_outputs(list(outputs))

    prediction = np.squeeze(prediction)
    if prediction.ndim == 3:
        prediction = prediction[0]

    # Transpose [channels, anchors] -> [anchors, channels] if needed
    if prediction.shape[0] in (4, 5, 84, 85) and prediction.shape[0] < prediction.shape[1]:
        prediction = prediction.transpose(1, 0)

    inferred_end2end = False
    if prediction.shape[-1] >= 6 and prediction.shape[0] <= 1000:
        boxes_xyxy = _convert_boxes(prediction[:, :4], box_format)
        confidences = prediction[:, 4].astype(np.float32)
        classes = prediction[:, 5].astype(np.int32)
        inferred_end2end = True
    else:
        boxes_xyxy, confidences, classes = _parse_yolo_matrix(
            prediction, confidence, has_objectness, box_format
        )

    if box_coordinates == 'normalized':
        image_height, image_width = image_shape[:2]
        boxes_xyxy[:, [0, 2]] *= image_width
        boxes_xyxy[:, [1, 3]] *= image_height
        boxes_xyxy[:, [0, 2]] = np.clip(boxes_xyxy[:, [0, 2]], 0, image_width)
        boxes_xyxy[:, [1, 3]] = np.clip(boxes_xyxy[:, [1, 3]], 0, image_height)
    elif box_coordinates in ('auto', 'input_pixels'):
        boxes_xyxy = scale_boxes_to_image(boxes_xyxy, input_size, image_shape, resize)
    else:
        raise ValueError(f"Unsupported detection box coordinate space: '{box_coordinates}'")

    mask = confidences >= confidence
    boxes_xyxy = boxes_xyxy[mask]
    confidences = confidences[mask]
    classes = classes[mask]

    skip_nms = is_end2end if is_end2end is not None else inferred_end2end
    if not skip_nms:
        boxes_xyxy, confidences, classes = nms_boxes(boxes_xyxy, confidences, classes, iou)

    return filter_by_classes(boxes_xyxy, confidences, classes, classes_list)


def _select_detr_pair(
    outputs: List[ndarray],
    output_names: Optional[Sequence[str]] = None,
) -> Tuple[ndarray, ndarray]:
    """Split DETR runtime outputs into (logits, boxes)."""
    if len(outputs) != 2:
        raise ValueError(
            f"detr_outputs expects two tensors (class logits and boxes), got {len(outputs)}"
        )

    names = list(output_names) if output_names and len(output_names) == len(outputs) else []
    if names:
        logits = next(
            (out for name, out in zip(names, outputs) if any(key in name.lower() for key in ('logit', 'label', 'cls'))),
            None,
        )
        boxes = next((out for name, out in zip(names, outputs) if 'box' in name.lower()), None)
        if logits is not None and boxes is not None:
            return logits, boxes

    first, second = outputs
    return (first, second) if first.shape[-1] >= second.shape[-1] else (second, first)


def _detr_squeeze_batch(tensor: ndarray) -> ndarray:
    """Drop leading batch dimension of DETR tensor."""
    squeezed = np.squeeze(tensor)
    if squeezed.ndim == 3:
        raise ValueError(
            f"detr_outputs handles single-frame batches only, got batch of {squeezed.shape[0]}"
        )
    if squeezed.ndim != 2:
        raise ValueError(f"detr_outputs expected a per-query matrix, got shape {squeezed.shape}")
    return squeezed


def _detr_class_scores(
    logits: ndarray,
    num_classes: Optional[int],
    score_activation: str = 'auto',
) -> ndarray:
    """Turn DETR class logits into per-class probabilities."""
    channels = logits.shape[-1]
    if num_classes is not None and channels not in (num_classes, num_classes + 1):
        raise ValueError(
            f"detr_outputs got {channels} logit channels for {num_classes} declared classes"
        )
    has_background = num_classes is not None and channels == num_classes + 1

    if score_activation == 'auto':
        activation = 'softmax' if has_background else 'sigmoid'
    elif score_activation in ('sigmoid', 'softmax'):
        activation = score_activation
    else:
        raise ValueError(f"Unsupported detection score activation: '{score_activation}'")

    if activation == 'softmax':
        scores = np.exp(logits - np.max(logits, axis=1, keepdims=True))
        scores = scores / scores.sum(axis=1, keepdims=True)
    else:
        scores = 1.0 / (1.0 + np.exp(-logits))

    return scores[:, 1:] if has_background else scores


def parse_detr_outputs(
    outputs: list[ndarray] | ndarray,
    confidence: float,
    input_size: Tuple[int, int],
    image_shape: Tuple[int, int, int],
    classes_list: Optional[Iterable[int]] = None,
    num_classes: Optional[int] = None,
    output_names: Optional[Sequence[str]] = None,
    box_format: str = 'cxcywh',
    box_coordinates: str = 'auto',
    score_activation: str = 'auto',
    resize: str = 'letterbox',
) -> ParsedDetections:
    """
    Parse DETR/RT-DETR set predictions (class logits plus boxes) into xyxy boxes.

    Args:
        outputs: The runtime outputs (pair of logits and boxes).
        confidence: Score threshold for query retention.
        input_size: Model input canvas size (width, height).
        image_shape: Original image shape (height, width, channels).
        classes_list: Optional list of class IDs to filter.
        num_classes: Declared class count.
        output_names: Runtime output names for pairing.
        box_format: 'cxcywh' or 'xyxy'.
        box_coordinates: 'auto', 'normalized' or 'input_pixels'.
        score_activation: 'sigmoid', 'softmax' or 'auto'.
        resize: 'letterbox' or 'stretch'.

    Returns:
        ParsedDetections: (boxes_xyxy, confidences, classes).
    """
    output_list = [outputs] if isinstance(outputs, ndarray) else list(outputs)
    logits, boxes = _select_detr_pair(output_list, output_names)

    scores = _detr_class_scores(_detr_squeeze_batch(logits), num_classes, score_activation)
    classes = np.argmax(scores, axis=1).astype(np.int32)
    confidences = scores[np.arange(len(scores)), classes].astype(np.float32)

    boxes_xyxy = _convert_boxes(_detr_squeeze_batch(boxes), box_format)
    if boxes_xyxy.shape[0] != len(classes):
        raise ValueError(
            f"detr_outputs got {boxes_xyxy.shape[0]} boxes for {len(classes)} class scores"
        )

    coordinates = box_coordinates
    if coordinates == 'auto':
        coordinates = 'normalized' if float(np.max(boxes_xyxy)) <= 1.05 else 'input_pixels'
    if coordinates == 'normalized':
        image_height, image_width = image_shape[:2]
        boxes_xyxy[:, [0, 2]] *= image_width
        boxes_xyxy[:, [1, 3]] *= image_height
    elif coordinates == 'input_pixels':
        boxes_xyxy = scale_boxes_to_image(boxes_xyxy, input_size, image_shape, resize)
    else:
        raise ValueError(f"Unsupported detection box coordinate space: '{coordinates}'")

    mask = confidences >= confidence
    boxes_xyxy, confidences, classes = boxes_xyxy[mask], confidences[mask], classes[mask]

    return filter_by_classes(boxes_xyxy, confidences, classes, classes_list)


__all__ = [
    "ParsedDetections",
    "filter_by_classes",
    "box_iou",
    "nms_boxes",
    "scale_boxes_to_image",
    "parse_yolo_outputs",
    "parse_detr_outputs",
]
