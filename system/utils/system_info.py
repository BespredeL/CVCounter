# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

import os
import platform
import subprocess
from shutil import disk_usage
from typing import Any

import psutil

from system.utils.bytesize import format_bytes
from system.utils.nvidia import (
    _cuda_runtime_ok,
    _find_nvidia_smi,
    _get_torch,
    _nvidia_smi_query,
    _parse_nvidia_smi_text,
)
from system.utils.paths import get_project_root
from system.utils.text import colored_text, pr_color


def get_system_info() -> dict[str | Any, str | int | Any]:
    """
    Get system information.

    Returns:
        dict: Host, memory, disk, and GPU metadata.
    """
    nvidia_info = {
        'nvidia_smi_version': None,
        'driver_version': None,
        'cuda_version': None,
        'gpu_name': None,
    }

    smi_cmd = _find_nvidia_smi()
    if smi_cmd:
        try:
            result = subprocess.run(
                [smi_cmd],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0 and result.stdout:
                nvidia_info.update(_parse_nvidia_smi_text(result.stdout))
        except (OSError, subprocess.TimeoutExpired):
            pass

    if not nvidia_info['driver_version']:
        nvidia_info['driver_version'] = _nvidia_smi_query('driver_version')

    if not nvidia_info['gpu_name']:
        nvidia_info['gpu_name'] = _nvidia_smi_query('name')

    torch = _get_torch()
    cuda_available = _cuda_runtime_ok()
    cuda_device_count = 0
    if cuda_available and torch is not None:
        try:
            cuda_device_count = torch.cuda.device_count()
            if not nvidia_info['gpu_name'] and cuda_device_count > 0:
                nvidia_info['gpu_name'] = torch.cuda.get_device_name(0)
        except Exception:
            cuda_device_count = 0

    virtual_memory = psutil.virtual_memory()._asdict()
    swap_memory = psutil.swap_memory()._asdict()
    disk_usages = disk_usage(get_project_root())._asdict()

    sys_info = {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": psutil.cpu_count(logical=False),
        "cpu_percent": f"{psutil.cpu_percent(interval=None)} %",

        "nvidia_smi_version": nvidia_info["nvidia_smi_version"],
        "driver_version": nvidia_info["driver_version"],
        "cuda_version": nvidia_info["cuda_version"],
        "gpu_name": nvidia_info["gpu_name"],
        "cuda_device_count": cuda_device_count,
        "py_torch_cuda_available": "Yes" if cuda_available else None,
        "py_torch_cuda_version": (getattr(torch.version, 'cuda', None) if torch and hasattr(torch, 'version') else None) or None,
        "py_torch_version": getattr(torch, '__version__', None),

        "virtual_memory": {
            "total": format_bytes(virtual_memory['total']),
            "available": format_bytes(virtual_memory['available']),
            "used": format_bytes(virtual_memory['used']),
            "free": format_bytes(virtual_memory['free']),
            "percent": f"{virtual_memory['percent']} %"
        },
        "swap_memory": {
            "total": format_bytes(swap_memory['total']),
            "used": format_bytes(swap_memory['used']),
            "free": format_bytes(swap_memory['free']),
            "percent": f"{swap_memory['percent']} %"
        },
        "disk_usage": {
            "total": format_bytes(disk_usages['total']),
            "used": format_bytes(disk_usages['used']),
            "free": format_bytes(disk_usages['free'])
        }
    }

    return sys_info


def should_run_startup_system_check() -> bool:
    """
    Return True when startup hooks should run in the current process.

    Werkzeug's debug reloader imports the application twice: a file-watcher
    parent and the worker child (WERKZEUG_RUN_MAIN=true). Running GPU checks
    in both processes duplicates console output.

    Args:
        None

    Returns:
        bool: True when startup hooks should run in the current process.
    """
    run_main = os.environ.get("WERKZEUG_RUN_MAIN")
    if run_main == "true":
        return True

    flask_debug = os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true")
    reload_disabled = os.environ.get("FLASK_RUN_RELOAD", "").lower() in ("0", "false")

    # Single process: no reloader, or explicit --no-reload
    if run_main is None and (not flask_debug or reload_disabled):
        return True

    return False


def system_check() -> None:
    """
    System check

    Args:
        None

    Returns:
        None
    """
    sys_info = get_system_info()

    def colored_value(value: str) -> str:
        """
        Colored value

        Args:
            value: str - The value to be colored.

        Returns:
            str: Colored value.
        """
        if value == "N/A":
            return colored_text(value, 'red')
        else:
            return colored_text(value, 'green')

    pr_color(f' * NVIDIA-SMI Version: {colored_value(sys_info["nvidia_smi_version"] or "N/A")}',
             'yellow')
    pr_color(f' * Driver Version: {colored_value(sys_info["driver_version"] or "N/A")}', 'yellow')
    pr_color(f' * CUDA Version: {colored_value(sys_info["cuda_version"] or "N/A")}', 'yellow')

    if sys_info["gpu_name"]:
        pr_color(f' * GPU: {colored_value(sys_info["gpu_name"])}', 'yellow')

    pr_color(f' * PyTorch CUDA Available: {colored_value(sys_info["py_torch_cuda_available"] or "N/A")}', 'yellow')
    if sys_info["cuda_device_count"]:
        pr_color(
            f' * CUDA Devices: {colored_value(str(sys_info["cuda_device_count"]))}',
            'yellow',
        )
    pr_color(f' * PyTorch CUDA Version: {colored_value(sys_info["py_torch_cuda_version"] or "N/A")}', 'yellow')

    pr_color(f' * PyTorch Version: {colored_value(sys_info["py_torch_version"] or "N/A")}', 'yellow')

    cuda_ready = bool(sys_info["py_torch_cuda_available"])
    driver_reported = bool(sys_info["driver_version"] or sys_info["nvidia_smi_version"])
    cuda_reported = bool(sys_info["cuda_version"] or sys_info["py_torch_cuda_version"])

    if cuda_ready or (driver_reported and cuda_reported and sys_info["py_torch_version"]):
        print(f'{colored_text(" * System Check Result:", "yellow")} {colored_text("PASSED", "green")}')
    else:
        print(f'{colored_text(" * System Check Result:", "yellow")} {colored_text("FAILED", "red")}')
        if not cuda_ready:
            print(f'{colored_text(" * TIP:", "cyan")} To enable GPU acceleration, install the official NVIDIA driver:')
            print(f'{colored_text("   ->", "cyan")} https://www.nvidia.com/Download/index.aspx')
