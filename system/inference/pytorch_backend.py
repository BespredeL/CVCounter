# -*- coding: utf-8 -*-
# ! python3

"""
PyTorch Inference Backend for CVCounter.
Supports CPU and NVIDIA GPU (CUDA) execution with automatic device management and FP16 option.
"""

from __future__ import annotations

import gc
from typing import Any, Optional
import numpy as np

from system.inference.base import BackendType, IInferenceBackend


class PyTorchBackend(IInferenceBackend):
    def __init__(self, device: str = "cpu", fp16: bool = False) -> None:
        self._device = device
        self._fp16 = fp16
        self._model = None
        self._torch = None
        self._backend_type = BackendType.PYTORCH_CUDA if "cuda" in device else BackendType.PYTORCH_CPU

    @property
    def backend_type(self) -> BackendType:
        return self._backend_type

    @property
    def device_name(self) -> str:
        return self._device

    def is_loaded(self) -> bool:
        return self._model is not None

    def load(self, model_source: Any, device: Optional[str] = None, **kwargs) -> None:
        import torch
        self._torch = torch

        if device is not None:
            self._device = device
            self._backend_type = BackendType.PYTORCH_CUDA if "cuda" in device else BackendType.PYTORCH_CPU

        if isinstance(model_source, torch.nn.Module):
            self._model = model_source
        elif callable(model_source):
            self._model = model_source()
        else:
            raise ValueError(f"Unsupported PyTorch model source: {type(model_source)}")

        self._model.to(self._device)
        self._model.eval()

        if self._fp16 and "cuda" in self._device:
            self._model.half()

    def unload(self) -> None:
        self._model = None
        if self._torch is not None and self._torch.cuda.is_available():
            self._torch.cuda.empty_cache()
        gc.collect()

    def predict(self, inputs: Any, **kwargs) -> Any:
        if self._model is None:
            raise RuntimeError("PyTorch model is not loaded in backend")

        torch = self._torch
        with torch.no_grad():
            if isinstance(inputs, np.ndarray):
                tensor = torch.from_numpy(inputs).to(self._device)
                if self._fp16 and "cuda" in self._device and tensor.dtype == torch.float32:
                    tensor = tensor.half()
                return self._model(tensor)
            elif isinstance(inputs, torch.Tensor):
                tensor = inputs.to(self._device)
                if self._fp16 and "cuda" in self._device and tensor.dtype == torch.float32:
                    tensor = tensor.half()
                return self._model(tensor)
            else:
                return self._model(inputs)
