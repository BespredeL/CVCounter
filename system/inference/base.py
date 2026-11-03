# -*- coding: utf-8 -*-
# ! python3

"""
Base contracts and definitions for Inference Backends in CVCounter.
Separates neural network architecture from inference runtime engines.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, Optional, Tuple
import numpy as np


class BackendType(str, Enum):
    PYTORCH_CUDA = "pytorch_cuda"
    PYTORCH_CPU = "pytorch_cpu"
    ONNX_CUDA = "onnx_cuda"
    ONNX_CPU = "onnx_cpu"
    TENSORRT = "tensorrt"


class IInferenceBackend(ABC):
    """Abstract interface for model execution backends."""

    @abstractmethod
    def load(self, model_source: Any, device: str = "cpu", **kwargs) -> None:
        """Load or compile model into this backend."""

    @abstractmethod
    def unload(self) -> None:
        """Free backend buffers and release hardware handles."""

    @abstractmethod
    def predict(self, inputs: Any, **kwargs) -> Any:
        """Execute raw forward pass on provided tensor or ndarray."""

    @abstractmethod
    def is_loaded(self) -> bool:
        """Check if backend is ready for inference."""

    @property
    @abstractmethod
    def backend_type(self) -> BackendType:
        """Return the BackendType identifier."""

    @property
    @abstractmethod
    def device_name(self) -> str:
        """Return device string (e.g. 'cuda:0', 'cpu')."""
