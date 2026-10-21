# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

"""
Canonical schema and alignment utilities for camera configurations.
Ensures unified parameter ordering, auto-injection of backend-specific options,
and preservation of custom user keys.
"""

import copy
from typing import Any, Dict, List, Optional, Tuple


# Master canonical sequence of known camera settings keys
CANONICAL_CAMERA_KEYS: List[str] = [
    # 1. Stream & General
    "label",
    "start_total_count",
    "video_path",
    "video_show_scale",
    "video_show_quality",
    "video_fps",
    "video_reconnect_attempts",
    # 2. Base Detector Parameters
    "model_type",
    "weights_path",
    "confidence",
    "iou",
    "device",
    "vid_stride",
    "indicator_mode",
    "indicator_size",
    # 3. Counting Areas (Zones)
    "counting_area",
    "counting_areas",
    "counting_area_color",
    # 4. Model & Backend-Specific Options
    "model_config_path",
    "input_size",
    "backend",
    "target",
    "providers",
    # 5. Classes Management
    "classes",
    # 6. Custom Fields (Detection-Specific)
    "custom_fields",
    # 7. Dataset Generation & Video Recording Subsystems
    "dataset_create",
    "recording",
]

# Baseline default values for common camera keys
CANONICAL_DEFAULTS: Dict[str, Any] = {
    "start_total_count": 0,
    "video_path": "",
    "video_show_scale": 70,
    "video_show_quality": 50,
    "video_fps": 0,
    "video_reconnect_attempts": 5,
    "model_type": "yolo",
    "weights_path": "config/ultralytics/models/yolov8n.pt",
    "confidence": 0.5,
    "iou": 0.7,
    "device": 0,
    "vid_stride": 1,
    "indicator_mode": "circle",
    "indicator_size": 10,
    "counting_area": [
        [0, 0],
        [100, 0],
        [100, 100],
        [0, 100]
    ],
    "counting_area_color": [67, 211, 255],
    "counting_areas": [
        {
            "points": [
                [0, 0],
                [100, 0],
                [100, 100],
                [0, 100]
            ],
            "color": [67, 211, 255]
        }
    ],
    "classes": {},
    "custom_fields": {},
    "dataset_create": {
        "enable": False,
        "probability": 0.1,
        "path": "storage/saved_images"
    },
    "recording": {
        "enable": False,
        "path": "storage/saved_recordings",
        "scale": 50,
        "quality": 70,
        "idle_timeout": 30
    }
}

# Backend-specific parameter expectations and defaults based on model_type
BACKEND_SPECIFIC_PARAMS: Dict[str, Dict[str, Any]] = {
    "opencv": {
        "input_size": 640,
        "backend": "DEFAULT",
        "target": "CPU",
    },
    "opencv_dnn": {
        "model_config_path": "",
        "input_size": 416,
    },
    "onnx": {
        "input_size": 640,
        "providers": ["CPUExecutionProvider"],
    },
    "onnxruntime": {
        "input_size": 640,
        "providers": ["CPUExecutionProvider"],
    },
    "openvino": {
        "input_size": 640,
        "device": "CPU",
    },
    "yolo": {},
    "ultralytics": {},
}


def align_camera_dict(
    camera_dict: Dict[str, Any],
    default_template: Optional[Dict[str, Any]] = None,
    location_id: Optional[str] = None,
    is_default_template: bool = False
) -> Dict[str, Any]:
    """
    Align a single camera (or detection_default) dictionary according to the canonical schema.

    - Canonical keys are placed in their fixed standard order.
    - Missing required/common parameters are filled from default_template or CANONICAL_DEFAULTS.
    - Backend-specific parameters corresponding to model_type are injected if absent.
    - Any unrecognized custom user keys are preserved at the end sorted alphabetically.

    Args:
        camera_dict: The source camera dictionary.
        default_template: Optional template dictionary (e.g. detection_default) for inherited values.
        location_id: Optional camera location identifier (used for default labels/paths).
        is_default_template: If True, indicates we are formatting detection_default itself.

    Returns:
        Dict[str, Any]: Canonicalized dictionary with ordered keys.
    """
    src = copy.deepcopy(camera_dict or {})
    fallback = default_template or {}
    aligned: Dict[str, Any] = {}

    # Determine model_type
    model_type = str(src.get("model_type") or fallback.get("model_type") or "yolo").lower()

    # Determine backend-specific keys to ensure
    backend_params = BACKEND_SPECIFIC_PARAMS.get(model_type, {})

    # 1. Fill missing baseline values into src
    if not is_default_template:
        if "label" not in src:
            src["label"] = fallback.get("label") or (f"Camera {location_id}" if location_id else "Camera")

    for key, default_val in CANONICAL_DEFAULTS.items():
        if is_default_template and key in ("label", "video_path", "start_total_count"):
            continue
        if key not in src:
            if key in fallback:
                src[key] = copy.deepcopy(fallback[key])
            else:
                src[key] = copy.deepcopy(default_val)
                if key == "dataset_create" and location_id:
                    src[key]["path"] = f"storage/saved_images/{location_id}"

    # Ensure backend-specific parameters if this model_type requires them
    for param_key, param_default in backend_params.items():
        if param_key not in src:
            if param_key in fallback:
                src[param_key] = copy.deepcopy(fallback[param_key])
            else:
                src[param_key] = copy.deepcopy(param_default)

    # 2. Place known canonical keys in exact order
    for canon_key in CANONICAL_CAMERA_KEYS:
        if canon_key in src:
            aligned[canon_key] = src[canon_key]

    # 3. Collect any non-canonical custom keys and append them sorted alphabetically
    canonical_set = set(CANONICAL_CAMERA_KEYS)
    custom_keys = sorted([k for k in src.keys() if k not in canonical_set])
    for custom_key in custom_keys:
        aligned[custom_key] = src[custom_key]

    return aligned


def align_full_config(full_config: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """
    Align detection_default and all detections in a full configuration dictionary.

    Args:
        full_config: Full configuration dictionary (from config.json).

    Returns:
        Tuple[Dict[str, Any], bool]: (aligned_config, has_changed)
    """
    if not isinstance(full_config, dict):
        return full_config, False

    aligned_config = copy.deepcopy(full_config)
    original_config = copy.deepcopy(full_config)

    # 1. Align detection_default if present
    default_template = aligned_config.get("detection_default")
    if isinstance(default_template, dict):
        aligned_default = align_camera_dict(default_template, is_default_template=True)
        aligned_config["detection_default"] = aligned_default
        default_template = aligned_default

    # 2. Align each camera in detections
    detections = aligned_config.get("detections")
    if isinstance(detections, dict):
        aligned_detections: Dict[str, Any] = {}
        for location_id, cam_dict in detections.items():
            if isinstance(cam_dict, dict):
                aligned_cam = align_camera_dict(
                    cam_dict,
                    default_template=default_template,
                    location_id=location_id,
                    is_default_template=False
                )
                aligned_detections[location_id] = aligned_cam
            else:
                aligned_detections[location_id] = cam_dict
        aligned_config["detections"] = aligned_detections

    has_changed = (aligned_config != original_config)
    return aligned_config, has_changed
