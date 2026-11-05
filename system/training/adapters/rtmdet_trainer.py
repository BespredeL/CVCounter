# -*- coding: utf-8 -*-
# ! python3

"""
RTMDet Training Provider for CVCounter.
Provides model catalog and integration hooks for OpenMMLab RTMDet models.
Training will be implemented under roadmap task EXT/TRAIN-RTMDET.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from system.training.base import (
    BaseTrainingProvider,
    TrainingCancelledError,
    TrainingRequest,
    TrainingResult,
)


DEFAULT_BASE_MODEL = "rtmdet_tiny.pth"

BASE_MODELS: dict[str, dict[str, Any]] = {
    "rtmdet_tiny.pth": {
        "name": "RTMDet-Tiny (COCO)",
        "task": "detect",
        "size_mb": 54.9,
        "speed": "Very Fast",
        "recommended": True,
        "description": "Ultra-fast OpenMMLab RTMDet-Tiny detector for edge devices and CPU.",
        "url": "https://download.openmmlab.com/mmdetection/v3.0/rtmdet/rtmdet_tiny_8xb32-300e_coco/rtmdet_tiny_8xb32-300e_coco_20220902_112414-78e30dcc.pth",
        "code_license": "Apache-2.0",
        "code_license_url": "https://github.com/open-mmlab/mmdetection/blob/main/LICENSE",
        "weights_license": "Apache-2.0 / Dataset-dependent",
        "weights_license_url": None,
        "dataset_license": "Mixed / Flickr Terms (images) & CC-BY-4.0 (annotations)",
        "dataset_license_url": "https://cocodataset.org/#termsofuse",
        "license_status": "unverified",
        "weights_license_status": "unverified",
        "license_url": "https://github.com/open-mmlab/mmdetection/blob/main/LICENSE",
        "source_url": "https://github.com/open-mmlab/mmdetection",
    },
    "rtmdet_s.pth": {
        "name": "RTMDet-S (COCO)",
        "task": "detect",
        "size_mb": 87.2,
        "speed": "Fast",
        "recommended": False,
        "description": "Fast OpenMMLab RTMDet-Small detector with an optimal speed/accuracy balance.",
        "url": "https://download.openmmlab.com/mmdetection/v3.0/rtmdet/rtmdet_s_8xb32-300e_coco/rtmdet_s_8xb32-300e_coco_20220905_161602-387a891e.pth",
        "code_license": "Apache-2.0",
        "code_license_url": "https://github.com/open-mmlab/mmdetection/blob/main/LICENSE",
        "weights_license": "Apache-2.0 / Dataset-dependent",
        "weights_license_url": None,
        "dataset_license": "Mixed / Flickr Terms (images) & CC-BY-4.0 (annotations)",
        "dataset_license_url": "https://cocodataset.org/#termsofuse",
        "license_status": "unverified",
        "weights_license_status": "unverified",
        "license_url": "https://github.com/open-mmlab/mmdetection/blob/main/LICENSE",
        "source_url": "https://github.com/open-mmlab/mmdetection",
    },
    "rtmdet_m.pth": {
        "name": "RTMDet-M (COCO)",
        "task": "detect",
        "size_mb": 213.9,
        "speed": "Medium",
        "recommended": False,
        "description": "Balanced OpenMMLab RTMDet-Medium detector for GPU inference.",
        "url": "https://download.openmmlab.com/mmdetection/v3.0/rtmdet/rtmdet_m_8xb32-300e_coco/rtmdet_m_8xb32-300e_coco_20220719_112220-229f527c.pth",
        "code_license": "Apache-2.0",
        "code_license_url": "https://github.com/open-mmlab/mmdetection/blob/main/LICENSE",
        "weights_license": "Apache-2.0 / Dataset-dependent",
        "weights_license_url": None,
        "dataset_license": "Mixed / Flickr Terms (images) & CC-BY-4.0 (annotations)",
        "dataset_license_url": "https://cocodataset.org/#termsofuse",
        "license_status": "unverified",
        "weights_license_status": "unverified",
        "license_url": "https://github.com/open-mmlab/mmdetection/blob/main/LICENSE",
        "source_url": "https://github.com/open-mmlab/mmdetection",
    },
    "rtmdet_l.pth": {
        "name": "RTMDet-L (COCO)",
        "task": "detect",
        "size_mb": 432.7,
        "speed": "Slow",
        "recommended": False,
        "description": "High-accuracy OpenMMLab RTMDet-Large detector with maximum mAP precision.",
        "url": "https://download.openmmlab.com/mmdetection/v3.0/rtmdet/rtmdet_l_8xb32-300e_coco/rtmdet_l_8xb32-300e_coco_20220719_112030-5a0be7c4.pth",
        "code_license": "Apache-2.0",
        "code_license_url": "https://github.com/open-mmlab/mmdetection/blob/main/LICENSE",
        "weights_license": "Apache-2.0 / Dataset-dependent",
        "weights_license_url": None,
        "dataset_license": "Mixed / Flickr Terms (images) & CC-BY-4.0 (annotations)",
        "dataset_license_url": "https://cocodataset.org/#termsofuse",
        "license_status": "unverified",
        "weights_license_status": "unverified",
        "license_url": "https://github.com/open-mmlab/mmdetection/blob/main/LICENSE",
        "source_url": "https://github.com/open-mmlab/mmdetection",
    },
}


class RTMDetTrainingProvider(BaseTrainingProvider):
    id: str = "rtmdet"
    tasks: tuple[str, ...] = ("detect",)
    dataset_formats: tuple[str, ...] = ("coco", "yolo")
    export_formats: tuple[str, ...] = ()
    BASE_MODELS = BASE_MODELS

    def train(self, request: TrainingRequest) -> TrainingResult:
        if request.cancel_check and request.cancel_check():
            raise TrainingCancelledError("Training was cancelled before start.")

        raise RuntimeError(
            "Training for RTMDet is not implemented yet. "
            "Planned for roadmap task EXT/TRAIN-RTMDET. "
            "Pretrained base models remain available for download and inference."
        )

    def export(self, weights: Path, export_format: str, device: str | int) -> Path:
        raise NotImplementedError(
            f"Provider '{self.id}' does not implement '{export_format}' export."
        )
