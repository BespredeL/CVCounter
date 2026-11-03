# -*- coding: utf-8 -*-
# ! python3

"""
Centralized Model Manager for CVCounter.
Provides registration, discovery, lazy loading, switching, and deletion of multi-architecture models.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from system.detection.interface import IDetector
from system.detection.registry import canonical_architecture, load_detector
from system.models.metadata import ModelMetadata

logger = logging.getLogger("cvcounter.models.manager")


class ModelManager:
    """Central model management registry and lifecycle controller."""

    def __init__(self, storage_dir: Optional[str | Path] = None) -> None:
        from system.utils.paths import get_project_root
        root = Path(get_project_root())
        self.storage_dir = Path(storage_dir or (root / "storage" / "models_meta"))
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._registry: dict[str, ModelMetadata] = {}
        self._active_detector: Optional[IDetector] = None
        self._active_model_id: Optional[str] = None
        self._load_registered_models()

    def _load_registered_models(self) -> None:
        for json_file in self.storage_dir.glob("*.json"):
            try:
                meta = ModelMetadata.load(json_file)
                self._registry[meta.model_id] = meta
            except Exception as e:
                logger.warning(f"Failed to load model metadata from {json_file.name}: {e}")

    def register_model(self, meta: ModelMetadata) -> None:
        """Register or update model metadata."""
        self._registry[meta.model_id] = meta
        save_path = self.storage_dir / f"{meta.model_id}.json"
        meta.save(save_path)

    def get_model(self, model_id: str) -> Optional[ModelMetadata]:
        return self._registry.get(model_id)

    def list_models(self, architecture: Optional[str] = None) -> list[dict[str, Any]]:
        """Return list of registered models with weights existence status."""
        result = []
        for meta in self._registry.values():
            if architecture and canonical_architecture(meta.architecture) != canonical_architecture(architecture):
                continue
            data = meta.to_dict()
            data["weights_exist"] = bool(meta.weights_path and Path(meta.weights_path).is_file())
            data["is_active"] = meta.model_id == self._active_model_id
            result.append(data)
        return result

    def get_active_model_info(self) -> Optional[dict[str, Any]]:
        if self._active_detector is not None and self._active_detector.is_loaded():
            return self._active_detector.get_model_info().to_dict()
        return None

    def load_model(
        self,
        model_id: str,
        device: str = "cpu",
        backend: Optional[str] = None,
        confidence: Optional[float] = None,
        iou: Optional[float] = None,
        **kwargs,
    ) -> IDetector:
        """
        Load selected model into memory.
        Automatically unloads any previously loaded model to prevent GPU memory leaks.
        """
        meta = self._registry.get(model_id)
        if not meta:
            raise ValueError(f"Model '{model_id}' is not registered in ModelManager")

        if not meta.weights_path or not Path(meta.weights_path).is_file():
            raise FileNotFoundError(f"Model weights file not found on disk: {meta.weights_path}")

        # Unload active detector if present
        if self._active_detector is not None:
            self._active_detector.unload()
            self._active_detector = None
            self._active_model_id = None

        load_kwargs: dict[str, Any] = dict(kwargs)
        load_kwargs["device"] = device
        if backend:
            load_kwargs["backend"] = backend
        if confidence is not None:
            load_kwargs["confidence"] = confidence
        if iou is not None:
            load_kwargs["iou"] = iou

        detector = load_detector(
            architecture=meta.architecture,
            weights=meta.weights_path,
            **load_kwargs,
        )

        if detector is None or not detector.is_loaded():
            raise RuntimeError(f"Failed to load detector for model '{model_id}'")

        self._active_detector = detector
        self._active_model_id = model_id
        return detector

    def switch_model(self, model_id: str, **kwargs) -> IDetector:
        """Alias for load_model with safety verification."""
        return self.load_model(model_id, **kwargs)

    def unload_active_model(self) -> None:
        """Unload active model and release hardware resources."""
        if self._active_detector is not None:
            self._active_detector.unload()
            self._active_detector = None
            self._active_model_id = None

    def delete_model(self, model_id: str, confirm: bool = False, delete_weights: bool = False) -> bool:
        """
        Delete a registered model from the registry.
        Requires explicit confirm=True.
        """
        if not confirm:
            raise ValueError("Model deletion requires explicit confirmation (confirm=True)")

        meta = self._registry.pop(model_id, None)
        if meta is None:
            return False

        if self._active_model_id == model_id:
            self.unload_active_model()

        meta_file = self.storage_dir / f"{model_id}.json"
        if meta_file.is_file():
            meta_file.unlink()

        if delete_weights and meta.weights_path and Path(meta.weights_path).is_file():
            Path(meta.weights_path).unlink()

        return True


# Global shared instance
model_manager = ModelManager()
