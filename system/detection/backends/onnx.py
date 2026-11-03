# -*- coding: utf-8 -*-
# ! python3

"""
ONNX Runtime session manager with dynamic Execution Provider resolution and graceful fallback.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union
import numpy as np
from numpy import ndarray

from system.detection.exceptions import ModelLoadingError, ModelNotFoundError
from system.utils.logger import Logger

logger = Logger()


class ONNXSession:
    """
    Encapsulates an onnxruntime.InferenceSession with dynamic provider selection,
    hardware telemetry, and automatic fallback from GPU/accelerators to CPU.
    """

    def __init__(
        self,
        intra_op_threads: int = 4,
    ) -> None:
        self._intra_op_threads = intra_op_threads
        self._session = None
        self._input_names: list[str] = []
        self._output_names: list[str] = []
        self._input_shapes: list[list[Any]] = []
        self._active_provider: Optional[str] = None
        self._weights_path: Optional[str] = None

    @property
    def is_loaded(self) -> bool:
        """True if the ONNX Runtime session is initialized."""
        return self._session is not None

    @property
    def active_provider(self) -> Optional[str]:
        """Name of the execution provider actively used by the session."""
        return self._active_provider

    @property
    def input_names(self) -> list[str]:
        """Names of model inputs."""
        return list(self._input_names)

    @property
    def output_names(self) -> list[str]:
        """Names of model outputs."""
        return list(self._output_names)

    @property
    def input_shapes(self) -> list[list[Any]]:
        """Input tensor shapes declared in model metadata."""
        return list(self._input_shapes)

    def load(
        self,
        weights: Union[str, Path],
        device: Optional[str] = None,
        providers: Optional[Sequence[str]] = None,
    ) -> None:
        """
        Load an ONNX model file and initialize InferenceSession.

        Args:
            weights: Path to .onnx model weights file.
            device: Optional device identifier ('cpu', 'cuda', 'cuda:0', etc.).
            providers: Optional explicit list of execution provider names.

        Raises:
            ModelNotFoundError: If the weights file does not exist.
            ModelLoadingError: If session creation fails across all candidate providers.
        """
        import onnxruntime as ort

        path = Path(weights)
        if not path.is_file():
            raise ModelNotFoundError(f"ONNX weights file not found: {weights}")

        self._weights_path = str(path)
        available_providers = ort.get_available_providers()
        candidate_providers = self._resolve_candidates(providers, device, available_providers)

        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = self._intra_op_threads
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        session = None
        selected_provider = None
        errors: list[str] = []

        # Try providers in candidate order; fallback if initialization fails
        for prov in candidate_providers:
            try:
                session = ort.InferenceSession(
                    self._weights_path,
                    sess_options=sess_options,
                    providers=[prov, "CPUExecutionProvider"] if prov != "CPUExecutionProvider" else ["CPUExecutionProvider"],
                )
                actual_providers = session.get_providers()
                selected_provider = actual_providers[0] if actual_providers else prov
                logger.info(f"ONNX session loaded successfully with provider: {selected_provider}")
                break
            except Exception as exc:
                err_msg = f"Failed to initialize ONNX provider '{prov}': {exc}"
                logger.warning(err_msg)
                errors.append(err_msg)

        if session is None:
            raise ModelLoadingError(
                f"Could not load ONNX model '{weights}' on any provider. Errors: {'; '.join(errors)}"
            )

        self._session = session
        self._active_provider = selected_provider
        self._input_names = [inp.name for inp in session.get_inputs()]
        self._output_names = [out.name for out in session.get_outputs()]
        self._input_shapes = [inp.shape for inp in session.get_inputs()]

    def unload(self) -> None:
        """Release session resources and clear tensor metadata."""
        self._session = None
        self._active_provider = None
        self._input_names.clear()
        self._output_names.clear()
        self._input_shapes.clear()
        self._weights_path = None

    def run(self, inputs: Union[ndarray, Dict[str, ndarray]]) -> List[ndarray]:
        """
        Execute forward inference pass on the input tensor(s).

        Args:
            inputs: Either a single 4D numpy array for the primary input,
                    or a mapping of input names to numpy arrays.

        Returns:
            List[ndarray]: Raw output tensors produced by the ONNX graph.
        """
        if self._session is None:
            raise RuntimeError("ONNX Runtime session is not loaded")

        if isinstance(inputs, ndarray):
            if not self._input_names:
                raise RuntimeError("ONNX session has no registered input tensors")
            feed_dict = {self._input_names[0]: inputs}
        elif isinstance(inputs, dict):
            feed_dict = inputs
        else:
            raise ValueError(f"Invalid inputs type for ONNXSession: {type(inputs)}")

        return self._session.run(self._output_names, feed_dict)

    # Compatibility alias for predict()
    def predict(self, inputs: Union[ndarray, Dict[str, ndarray]], **kwargs: Any) -> List[ndarray]:
        """Forward alias for run()."""
        return self.run(inputs)

    @staticmethod
    def _resolve_candidates(
        configured_providers: Optional[Sequence[str]],
        device: Optional[str],
        available_providers: Sequence[str],
    ) -> List[str]:
        """
        Determine prioritized list of candidate execution providers.
        """
        candidates: List[str] = []

        if configured_providers:
            for prov in configured_providers:
                if prov in available_providers and prov not in candidates:
                    candidates.append(prov)

        if not candidates and device is not None:
            device_str = str(device).lower().strip()
            use_cuda = device_str not in ("", "cpu", "none") and not device_str.startswith("-")
            if use_cuda and "CUDAExecutionProvider" in available_providers:
                candidates.append("CUDAExecutionProvider")

        if "CPUExecutionProvider" in available_providers and "CPUExecutionProvider" not in candidates:
            candidates.append("CPUExecutionProvider")
        elif not candidates:
            candidates.append("CPUExecutionProvider")

        return candidates


__all__ = ["ONNXSession"]
