# -*- coding: utf-8 -*-
# ! python3

"""
ONNX Runtime Backend for CVCounter.
Supports CPUExecutionProvider and CUDAExecutionProvider with tensor feeding and shape tracking.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np

from system.inference.base import BackendType, IInferenceBackend


class ONNXBackend(IInferenceBackend):
    def __init__(self, device: str = "cpu", intra_op_threads: int = 4) -> None:
        self._device = device
        self._intra_op_threads = intra_op_threads
        self._session = None
        self._input_names: list[str] = []
        self._output_names: list[str] = []
        self._backend_type = BackendType.ONNX_CUDA if "cuda" in device else BackendType.ONNX_CPU

    @property
    def backend_type(self) -> BackendType:
        return self._backend_type

    @property
    def device_name(self) -> str:
        return self._device

    def is_loaded(self) -> bool:
        return self._session is not None

    def load(self, model_source: Any, device: Optional[str] = None, **kwargs) -> None:
        import onnxruntime as ort

        if device is not None:
            self._device = device
            self._backend_type = BackendType.ONNX_CUDA if "cuda" in device else BackendType.ONNX_CPU

        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = self._intra_op_threads
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"] if "cuda" in self._device else ["CPUExecutionProvider"]

        weights_path = str(model_source)
        if not Path(weights_path).is_file():
            raise FileNotFoundError(f"ONNX weights file not found: {weights_path}")

        self._session = ort.InferenceSession(weights_path, sess_options=sess_options, providers=providers)
        self._input_names = [inp.name for inp in self._session.get_inputs()]
        self._output_names = [out.name for out in self._session.get_outputs()]

    def unload(self) -> None:
        self._session = None
        self._input_names.clear()
        self._output_names.clear()

    def predict(self, inputs: Any, **kwargs) -> list[np.ndarray]:
        if self._session is None:
            raise RuntimeError("ONNX Runtime session is not loaded")

        if isinstance(inputs, np.ndarray):
            feed_dict = {self._input_names[0]: inputs}
        elif isinstance(inputs, dict):
            feed_dict = inputs
        else:
            raise ValueError(f"Invalid inputs type for ONNXBackend: {type(inputs)}")

        return self._session.run(self._output_names, feed_dict)
