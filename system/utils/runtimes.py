# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from __future__ import annotations

import importlib.metadata
import importlib.util
import os
import subprocess
import sys
import threading
from typing import Any, Dict, List, Optional


PACKAGE_BUNDLES: Dict[str, Dict[str, Any]] = {
    'onnx_export': {
        'name': 'ONNX Export & Tools',
        'description': 'Tools for exporting YOLO models to ONNX and optimizing graphs (onnx, onnxslim)',
        'packages': ['onnx>=1.16.0', 'onnxslim>=0.1.30'],
        'requires_gpu': False,
    },
    'onnx_runtime_gpu': {
        'name': 'ONNX Runtime (CUDA GPU)',
        'description': 'High-performance ONNX Runtime with NVIDIA CUDA acceleration',
        'packages': ['onnxruntime-gpu>=1.18.0'],
        'requires_gpu': True,
    },
    'tensorrt': {
        'name': 'TensorRT Acceleration',
        'description': 'NVIDIA TensorRT runtime and export package for Ultra-fast GPU inference',
        'packages': ['tensorrt>=8.6.0', 'cuda-python'],
        'requires_gpu': True,
    },
    'openvino': {
        'name': 'Intel OpenVINO',
        'description': 'Intel OpenVINO runtime for Intel CPU and iGPU/dGPU acceleration',
        'packages': ['openvino>=2024.0.0'],
        'requires_gpu': False,
    },
}


def is_package_installed(package_name: str) -> bool:
    """Check if a Python package is installed."""
    try:
        importlib.metadata.version(package_name)
        return True
    except (importlib.metadata.PackageNotFoundError, Exception):
        # Fallback to module spec check
        try:
            return importlib.util.find_spec(package_name.replace('-', '_')) is not None
        except Exception:
            return False


def get_package_version(package_name: str) -> Optional[str]:
    """Get the installed version of a Python package."""
    try:
        return importlib.metadata.version(package_name)
    except Exception:
        try:
            mod = __import__(package_name.replace('-', '_'))
            return getattr(mod, '__version__', None)
        except Exception:
            return None


def get_gpu_info() -> Dict[str, Any]:
    """Get GPU and CUDA information."""
    info: Dict[str, Any] = {
        'has_nvidia_gpu': False,
        'cuda_available': False,
        'device_name': None,
        'cuda_version': None,
        'driver_version': None,
        'device_count': 0,
    }

    try:
        from system.utils.utils import _nvidia_smi_query
        name = _nvidia_smi_query('name')
        driver = _nvidia_smi_query('driver_version')
        if name:
            info['has_nvidia_gpu'] = True
            info['device_name'] = name.split('\n')[0].strip()
        if driver:
            info['driver_version'] = driver.split('\n')[0].strip()
    except Exception:
        pass

    try:
        import torch
        if torch.cuda.is_available():
            info['cuda_available'] = True
            info['device_count'] = torch.cuda.device_count()
            if not info['device_name'] and info['device_count'] > 0:
                info['device_name'] = torch.cuda.get_device_name(0)
            info['cuda_version'] = torch.version.cuda
            info['has_nvidia_gpu'] = True
    except Exception:
        pass

    return info


def get_runtime_status() -> Dict[str, Any]:
    """Get full status of inference runtimes and hardware."""
    gpu = get_gpu_info()

    # ONNX & ONNX Runtime
    onnx_installed = is_package_installed('onnx')
    onnx_version = get_package_version('onnx')
    onnxslim_installed = is_package_installed('onnxslim')

    ort_installed = False
    ort_version = None
    ort_providers: List[str] = []
    try:
        import onnxruntime as ort
        ort_installed = True
        ort_version = getattr(ort, '__version__', None)
        ort_providers = ort.get_available_providers()
    except Exception:
        pass

    # TensorRT
    trt_installed = False
    trt_version = None
    try:
        import tensorrt as trt
        trt_installed = True
        trt_version = getattr(trt, '__version__', None)
    except Exception:
        pass

    # PyTorch
    torch_installed = False
    torch_version = None
    try:
        import torch
        torch_installed = True
        torch_version = getattr(torch, '__version__', None)
    except Exception:
        pass

    # OpenVINO
    openvino_installed = False
    openvino_version = None
    try:
        import openvino
        openvino_installed = True
        openvino_version = getattr(openvino, '__version__', None)
    except Exception:
        pass

    # Ultralytics
    ultralytics_installed = is_package_installed('ultralytics')
    ultralytics_version = get_package_version('ultralytics')

    packages_status = {
        'onnx': {'installed': onnx_installed, 'version': onnx_version},
        'onnxslim': {'installed': onnxslim_installed, 'version': get_package_version('onnxslim')},
        'onnxruntime': {'installed': ort_installed, 'version': ort_version, 'providers': ort_providers},
        'tensorrt': {'installed': trt_installed, 'version': trt_version},
        'torch': {'installed': torch_installed, 'version': torch_version, 'cuda': gpu['cuda_available']},
        'ultralytics': {'installed': ultralytics_installed, 'version': ultralytics_version},
        'openvino': {'installed': openvino_installed, 'version': openvino_version},
    }

    can_export_onnx = bool(ultralytics_installed and onnx_installed)
    can_export_engine = bool(ultralytics_installed and trt_installed and gpu['has_nvidia_gpu'])
    can_run_engine = bool(trt_installed and gpu['has_nvidia_gpu'])

    return {
        'gpu': gpu,
        'packages': packages_status,
        'onnx': {
            'export_ready': can_export_onnx,
            'inference_ready': ort_installed,
            'version': ort_version or onnx_version,
            'providers': ort_providers,
        },
        'tensorrt': {
            'export_ready': can_export_engine,
            'inference_ready': can_run_engine,
            'version': trt_version,
            'supported_on_hardware': gpu['has_nvidia_gpu'],
        },
        'bundles': PACKAGE_BUNDLES,
    }


class RuntimeManager:
    """Manager for installing AI runtime dependencies in the background."""

    _instance: Optional[RuntimeManager] = None
    _lock = threading.Lock()

    def __new__(cls) -> RuntimeManager:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_state()
            return cls._instance

    def _init_state(self) -> None:
        self.state_lock = threading.Lock()
        self.status = 'idle'  # 'idle' | 'running' | 'success' | 'error'
        self.active_bundle: Optional[str] = None
        self.logs: List[str] = []
        self.error_message: Optional[str] = None
        self.worker_thread: Optional[threading.Thread] = None

    def get_install_status(self) -> Dict[str, Any]:
        with self.state_lock:
            return {
                'status': self.status,
                'bundle': self.active_bundle,
                'logs': list(self.logs),
                'error': self.error_message,
            }

    def start_install(self, bundle_name: str) -> Dict[str, Any]:
        """Start background pip installation of the requested bundle."""
        if bundle_name not in PACKAGE_BUNDLES:
            return {
                'ok': False,
                'error': f"Unknown bundle '{bundle_name}'. Available: {list(PACKAGE_BUNDLES.keys())}",
            }

        bundle_def = PACKAGE_BUNDLES[bundle_name]
        gpu_info = get_gpu_info()
        if bundle_def.get('requires_gpu') and not gpu_info['has_nvidia_gpu']:
            return {
                'ok': False,
                'error': f"Bundle '{bundle_name}' requires an NVIDIA GPU, but none was detected in the system.",
            }

        with self.state_lock:
            if self.status == 'running':
                return {
                    'ok': False,
                    'error': f"An installation job is already running for bundle '{self.active_bundle}'.",
                }

            self.status = 'running'
            self.active_bundle = bundle_name
            self.logs = [f"Starting installation of {bundle_def['name']}..."]
            self.error_message = None

            self.worker_thread = threading.Thread(
                target=self._run_install_worker,
                args=(bundle_name, bundle_def['packages']),
                daemon=True,
            )
            self.worker_thread.start()

        return {'ok': True, 'bundle': bundle_name, 'status': 'running'}

    def _run_install_worker(self, bundle_name: str, packages: List[str]) -> None:
        """Worker thread executing pip install."""
        python_exe = sys.executable
        cmd = [python_exe, '-m', 'pip', 'install'] + packages

        self._append_log(f"Executing: {' '.join(cmd)}")
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

            if process.stdout:
                for line in iter(process.stdout.readline, ''):
                    stripped = line.rstrip()
                    if stripped:
                        self._append_log(stripped)

            process.wait()
            ret_code = process.returncode

            with self.state_lock:
                if ret_code == 0:
                    self.status = 'success'
                    self.logs.append(f"Successfully installed bundle '{bundle_name}'!")
                else:
                    self.status = 'error'
                    self.error_message = f"pip install exited with code {ret_code}"
                    self.logs.append(f"Error: {self.error_message}")
        except Exception as exc:
            with self.state_lock:
                self.status = 'error'
                self.error_message = str(exc)
                self.logs.append(f"Exception during installation: {exc}")

    def _append_log(self, text: str) -> None:
        with self.state_lock:
            self.logs.append(text)
            # Limit log buffer to last 500 lines
            if len(self.logs) > 500:
                self.logs = self.logs[-500:]


# Global runtime manager singleton
runtime_manager = RuntimeManager()
