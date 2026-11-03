# -*- coding: utf-8 -*-
# ! python3

"""
Hardware and Backend status diagnostics for CVCounter.
Provides independent health checks for PyTorch, ONNX Runtime, and TensorRT.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("cvcounter.inference.status")


def is_pytorch_installed() -> bool:
    try:
        import torch
        return True
    except ImportError:
        return False


def is_pytorch_cuda_available() -> bool:
    try:
        import torch
        return bool(torch.cuda.is_available() and torch.cuda.device_count() > 0)
    except Exception:
        return False


def is_pytorch_cpu_available() -> bool:
    return is_pytorch_installed()


def get_cuda_device_info(device_index: int = 0) -> dict[str, Any]:
    """Retrieve detailed information about a specific CUDA device."""
    if not is_pytorch_cuda_available():
        return {'available': False, 'device_count': 0}

    import torch
    count = torch.cuda.device_count()
    if device_index >= count:
        device_index = 0

    try:
        props = torch.cuda.get_device_properties(device_index)
        total_memory_mb = props.total_memory / (1024 * 1024)
        allocated_mb = torch.cuda.memory_allocated(device_index) / (1024 * 1024)
        reserved_mb = torch.cuda.memory_reserved(device_index) / (1024 * 1024)
        free_mb = total_memory_mb - reserved_mb

        return {
            'available': True,
            'device_count': count,
            'index': device_index,
            'name': props.name,
            'compute_capability': f"{props.major}.{props.minor}",
            'total_memory_mb': round(total_memory_mb, 2),
            'allocated_mb': round(allocated_mb, 2),
            'reserved_mb': round(reserved_mb, 2),
            'free_memory_mb': round(free_mb, 2),
        }
    except Exception as exc:
        return {
            'available': True,
            'device_count': count,
            'error': str(exc),
        }


def is_onnxruntime_installed() -> bool:
    try:
        import onnxruntime
        return True
    except ImportError:
        return False


def get_onnxruntime_providers() -> list[str]:
    try:
        import onnxruntime
        return onnxruntime.get_available_providers()
    except Exception:
        return []


def is_onnx_cuda_available() -> bool:
    providers = get_onnxruntime_providers()
    return "CUDAExecutionProvider" in providers and is_pytorch_cuda_available()


def is_onnx_cpu_available() -> bool:
    providers = get_onnxruntime_providers()
    return "CPUExecutionProvider" in providers


def is_tensorrt_available() -> bool:
    try:
        import tensorrt  # noqa: F401
        return is_pytorch_cuda_available()
    except ImportError:
        return False


def get_system_backend_status() -> dict[str, Any]:
    """Return health report for all 5 inference backends."""
    cuda_info = get_cuda_device_info(0)
    ort_providers = get_onnxruntime_providers()

    return {
        'pytorch_cuda': {
            'supported': is_pytorch_cuda_available(),
            'device_info': cuda_info if is_pytorch_cuda_available() else None,
        },
        'pytorch_cpu': {
            'supported': is_pytorch_cpu_available(),
        },
        'onnx_cuda': {
            'supported': is_onnx_cuda_available(),
            'available_providers': ort_providers,
        },
        'onnx_cpu': {
            'supported': is_onnx_cpu_available(),
            'available_providers': ort_providers,
        },
        'tensorrt': {
            'supported': is_tensorrt_available(),
            'gpu_ready': cuda_info.get('available', False),
        },
    }


def resolve_backend(requested_backend: Optional[str], requested_device: Optional[str] = "cuda") -> tuple[str, str]:
    """
    Resolve backend and device.
    If GPU/CUDA requested but unavailable, does NOT silently change backend without warning.
    Returns: (resolved_backend, resolved_device)
    """
    req_backend = (requested_backend or "pytorch").strip().lower()
    req_device = str(requested_device or "cpu").strip().lower()

    if "cuda" in req_device or req_device.isdigit():
        if not is_pytorch_cuda_available():
            raise RuntimeError(
                f"Requested device '{requested_device}' with backend '{requested_backend}', "
                f"but NVIDIA CUDA is not available on this machine. "
                f"Please select 'cpu' device or verify CUDA drivers."
            )
        dev = "cuda" if not req_device.isdigit() else f"cuda:{req_device}"
    else:
        dev = "cpu"

    if req_backend in ("onnx", "onnxruntime"):
        if dev.startswith("cuda") and not is_onnx_cuda_available():
            raise RuntimeError(
                "Requested ONNX Runtime CUDA, but CUDAExecutionProvider is not available in onnxruntime. "
                "Install onnxruntime-gpu or configure device='cpu'."
            )
        return "onnx", dev

    if req_backend in ("tensorrt", "trt"):
        if not is_tensorrt_available():
            raise RuntimeError(
                "Requested TensorRT backend, but 'tensorrt' python package is not installed "
                "or NVIDIA GPU is not available."
            )
        return "tensorrt", dev

    return "pytorch", dev
