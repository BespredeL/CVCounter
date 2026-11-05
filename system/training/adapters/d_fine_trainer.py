# -*- coding: utf-8 -*-
# ! python3

"""
D-FINE Training Provider for CVCounter.
Provides model catalog and integration hooks for Peterande/D-FINE models.
Training will be implemented under roadmap task EXT/TRAIN-D-FINE.
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


DEFAULT_BASE_MODEL = "dfine_n_coco.pth"

BASE_MODELS: dict[str, dict[str, Any]] = {
    "dfine_n_coco.pth": {
        "name": "D-FINE Nano (COCO)",
        "task": "detect",
        "size_mb": 14.8,
        "speed": "Very Fast",
        "recommended": True,
        "description": "Ultra-lightweight Peterande D-FINE Nano Real-Time Transformer for embedded systems.",
        "url": "https://github.com/Peterande/storage/releases/download/dfinev1.0/dfine_n_coco.pth",
        "code_license": "Apache-2.0",
        "code_license_url": "https://github.com/Peterande/D-FINE/blob/master/LICENSE",
        "weights_license": "Apache-2.0 / Dataset-dependent",
        "weights_license_url": None,
        "dataset_license": "Mixed / Flickr Terms (images) & CC-BY-4.0 (annotations)",
        "dataset_license_url": "https://cocodataset.org/#termsofuse",
        "license_status": "unverified",
        "weights_license_status": "unverified",
        "license_url": "https://github.com/Peterande/D-FINE/blob/master/LICENSE",
        "source_url": "https://github.com/Peterande/D-FINE",
    },
    "dfine_s_coco.pth": {
        "name": "D-FINE Small (COCO)",
        "task": "detect",
        "size_mb": 39.9,
        "speed": "Fast",
        "recommended": False,
        "description": "Compact D-FINE Small detector with high bounding box localization precision.",
        "url": "https://github.com/Peterande/storage/releases/download/dfinev1.0/dfine_s_coco.pth",
        "code_license": "Apache-2.0",
        "code_license_url": "https://github.com/Peterande/D-FINE/blob/master/LICENSE",
        "weights_license": "Apache-2.0 / Dataset-dependent",
        "weights_license_url": None,
        "dataset_license": "Mixed / Flickr Terms (images) & CC-BY-4.0 (annotations)",
        "dataset_license_url": "https://cocodataset.org/#termsofuse",
        "license_status": "unverified",
        "weights_license_status": "unverified",
        "license_url": "https://github.com/Peterande/D-FINE/blob/master/LICENSE",
        "source_url": "https://github.com/Peterande/D-FINE",
    },
    "dfine_m_coco.pth": {
        "name": "D-FINE Medium (COCO)",
        "task": "detect",
        "size_mb": 75.4,
        "speed": "Medium",
        "recommended": False,
        "description": "Balanced D-FINE Medium detector with superior detection accuracy.",
        "url": "https://github.com/Peterande/storage/releases/download/dfinev1.0/dfine_m_coco.pth",
        "code_license": "Apache-2.0",
        "code_license_url": "https://github.com/Peterande/D-FINE/blob/master/LICENSE",
        "weights_license": "Apache-2.0 / Dataset-dependent",
        "weights_license_url": None,
        "dataset_license": "Mixed / Flickr Terms (images) & CC-BY-4.0 (annotations)",
        "dataset_license_url": "https://cocodataset.org/#termsofuse",
        "license_status": "unverified",
        "weights_license_status": "unverified",
        "license_url": "https://github.com/Peterande/D-FINE/blob/master/LICENSE",
        "source_url": "https://github.com/Peterande/D-FINE",
    },
    "dfine_l_coco.pth": {
        "name": "D-FINE Large (COCO)",
        "task": "detect",
        "size_mb": 120.2,
        "speed": "Slow",
        "recommended": False,
        "description": "High-accuracy D-FINE Large architecture for server inference.",
        "url": "https://github.com/Peterande/storage/releases/download/dfinev1.0/dfine_l_coco.pth",
        "code_license": "Apache-2.0",
        "code_license_url": "https://github.com/Peterande/D-FINE/blob/master/LICENSE",
        "weights_license": "Apache-2.0 / Dataset-dependent",
        "weights_license_url": None,
        "dataset_license": "Mixed / Flickr Terms (images) & CC-BY-4.0 (annotations)",
        "dataset_license_url": "https://cocodataset.org/#termsofuse",
        "license_status": "unverified",
        "weights_license_status": "unverified",
        "license_url": "https://github.com/Peterande/D-FINE/blob/master/LICENSE",
        "source_url": "https://github.com/Peterande/D-FINE",
    },
    "dfine_x_coco.pth": {
        "name": "D-FINE X-Large (COCO)",
        "task": "detect",
        "size_mb": 240.4,
        "speed": "Heavy",
        "recommended": False,
        "description": "Maximum accuracy D-FINE X-Large architecture for demanding detection tasks.",
        "url": "https://github.com/Peterande/storage/releases/download/dfinev1.0/dfine_x_coco.pth",
        "code_license": "Apache-2.0",
        "code_license_url": "https://github.com/Peterande/D-FINE/blob/master/LICENSE",
        "weights_license": "Apache-2.0 / Dataset-dependent",
        "weights_license_url": None,
        "dataset_license": "Mixed / Flickr Terms (images) & CC-BY-4.0 (annotations)",
        "dataset_license_url": "https://cocodataset.org/#termsofuse",
        "license_status": "unverified",
        "weights_license_status": "unverified",
        "license_url": "https://github.com/Peterande/D-FINE/blob/master/LICENSE",
        "source_url": "https://github.com/Peterande/D-FINE",
    },
}


class DFINETrainingProvider(BaseTrainingProvider):
    id: str = "d_fine"
    tasks: tuple[str, ...] = ("detect",)
    dataset_formats: tuple[str, ...] = ("coco", "yolo")
    export_formats: tuple[str, ...] = ()
    BASE_MODELS = BASE_MODELS

    def train(self, request: TrainingRequest) -> TrainingResult:
        if request.cancel_check and request.cancel_check():
            raise TrainingCancelledError("Training was cancelled before start.")

        raise RuntimeError(
            "Training for D-FINE is not implemented yet. "
            "Planned for roadmap task EXT/TRAIN-D-FINE. "
            "Pretrained base models remain available for download and inference."
        )

    def export(self, weights: Path, export_format: str, device: str | int) -> Path:
        raise NotImplementedError(
            f"Provider '{self.id}' does not implement '{export_format}' export."
        )
