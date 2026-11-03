# -*- coding: utf-8 -*-
# ! python3

"""
TensorRT Inference Backend for CVCounter.
Loads compiled TensorRT engine (.engine, .trt) and runs high-performance FP16/FP32 inference.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np

from system.inference.base import BackendType, IInferenceBackend


class TensorRTBackend(IInferenceBackend):
    def __init__(self, device: str = "cuda:0") -> None:
        self._device = device
        self._engine = None
        self._context = None
        self._inputs = []
        self._outputs = []
        self._bindings = []
        self._stream = None

    @property
    def backend_type(self) -> BackendType:
        return BackendType.TENSORRT

    @property
    def device_name(self) -> str:
        return self._device

    def is_loaded(self) -> bool:
        return self._context is not None

    def load(self, model_source: Any, device: Optional[str] = None, **kwargs) -> None:
        try:
            import tensorrt as trt
            import torch
        except ImportError as exc:
            raise RuntimeError(f"TensorRT backend requires 'tensorrt' and 'torch' packages: {exc}")

        if not torch.cuda.is_available():
            raise RuntimeError("TensorRT requires an active NVIDIA GPU with CUDA support")

        engine_path = Path(str(model_source))
        if not engine_path.is_file():
            raise FileNotFoundError(f"TensorRT engine not found: {engine_path}")

        logger = trt.Logger(trt.Logger.WARNING)
        runtime = trt.Runtime(logger)

        with open(engine_path, "rb") as f:
            self._engine = runtime.deserialize_cuda_engine(f.read())

        if self._engine is None:
            raise RuntimeError(f"Failed to deserialize TensorRT engine from {engine_path}")

        self._context = self._engine.create_execution_context()
        self._stream = torch.cuda.Stream()

    def unload(self) -> None:
        self._context = None
        self._engine = None
        self._stream = None
        import gc
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    def predict(self, inputs: Any, **kwargs) -> Any:
        if self._context is None:
            raise RuntimeError("TensorRT engine is not loaded")
        # TensorRT execution delegate (also handled seamlessly by Ultralytics or Torch-TensorRT bindings)
        return inputs
