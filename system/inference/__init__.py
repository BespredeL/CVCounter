# -*- coding: utf-8 -*-
# ! python3

from system.inference.base import BackendType, IInferenceBackend
from system.inference.pytorch_backend import PyTorchBackend
from system.inference.onnx_backend import ONNXBackend
from system.inference.tensorrt_backend import TensorRTBackend
from system.inference.status import (
    get_cuda_device_info,
    get_onnxruntime_providers,
    get_system_backend_status,
    is_onnx_cpu_available,
    is_onnx_cuda_available,
    is_onnxruntime_installed,
    is_pytorch_cpu_available,
    is_pytorch_cuda_available,
    is_pytorch_installed,
    is_tensorrt_available,
    resolve_backend,
)

__all__ = [
    'BackendType',
    'IInferenceBackend',
    'PyTorchBackend',
    'ONNXBackend',
    'TensorRTBackend',
    'get_cuda_device_info',
    'get_onnxruntime_providers',
    'get_system_backend_status',
    'is_onnx_cpu_available',
    'is_onnx_cuda_available',
    'is_onnxruntime_installed',
    'is_pytorch_cpu_available',
    'is_pytorch_cuda_available',
    'is_pytorch_installed',
    'is_tensorrt_available',
    'resolve_backend',
]
