# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 22.03.2024
# Updated: 08.06.2026
# Website: https://bespredel.name

import os
import re
import subprocess
from shutil import disk_usage
import platform
from typing import Any, Dict

import psutil
import torch
from flask import request


def is_ajax() -> bool:
    """Check if the request is an AJAX request."""
    return str(request.headers.get('X-Requested-With')).lower() == 'XMLHttpRequest'.lower()


def slug(s: str) -> str:
    """
    Create slug

    Args:
        s (str): The text to be slugged.

    Returns:
        str: Slug string
    """
    s = s.lower().strip()
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[\s_-]+', '-', s)
    s = re.sub(r'^-+|-+$', '', s)
    return s


def pr_color(text: str, color: str) -> None:
    """
    Print with color

    Args:
        text (str): The text to be printed.
        color (str): The color to print the text in.

    Returns:
        None
    """
    colors = {
        'red': "\033[91m",
        'green': "\033[92m",
        'yellow': "\033[93m",
        'cyan': "\033[96m",
        'light_gray': "\033[97m",
        'black': "\033[98m"
    }
    if color not in colors:
        raise ValueError(f"Invalid color '{color}'. Valid options are: {', '.join(colors.keys())}")
    color_code = colors[color]
    print(f"{color_code}{text}\033[00m")


def colored_text(text: str, color: str) -> str:
    """
    Colored text

    Args:
        text (str): The text to be printed.
        color (str): The color to print the text in.

    Returns:
        str: Colored text
    """
    colors = {
        'red': "\033[91m",
        'green': "\033[92m",
        'yellow': "\033[93m",
        'cyan': "\033[96m",
        'light_gray': "\033[97m",
        'black': "\033[98m"
    }
    if color not in colors:
        raise ValueError(f"Invalid color '{color}'. Valid options are: {', '.join(colors.keys())}")
    color_code = colors.get(color, "\033[97m")  # Default to light gray if color not found
    return "{}{}\033[00m".format(color_code, text)


def format_bytes(size: int) -> str:
    """
    Format bytes to a human-readable size

    Args:
        size (int): The size to be formatted.

    Returns:
        str: The formatted size.
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"


def _nvidia_smi_query(field: str) -> str | None:
    """Read one GPU field via the stable nvidia-smi CSV query interface."""
    try:
        result = subprocess.run(
            ['nvidia-smi', f'--query-gpu={field}', '--format=csv,noheader,nounits'],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if result.returncode != 0:
        return None

    line = result.stdout.strip().splitlines()
    if not line:
        return None

    value = line[0].strip()
    if not value or value.upper() == 'N/A':
        return None
    return value


def _parse_nvidia_smi_text(stdout: str) -> dict[str, str | None]:
    """
    Parse human-readable nvidia-smi output.

    Driver 6xx renamed header fields to KMD Version / CUDA UMD Version.
    """
    merged = stdout.replace('\n', ' ')

    def _match(pattern: str) -> str | None:
        found = re.search(pattern, merged, flags=re.IGNORECASE)
        return found.group(1) if found else None

    return {
        'nvidia_smi_version': _match(r'NVIDIA-SMI\s+([\d.]+)'),
        'driver_version': _match(r'(?:Driver Version|KMD Version):\s*([\d.]+)'),
        'cuda_version': _match(r'CUDA(?: UMD)? Version:\s*([\d.]+)'),
    }


def _cuda_runtime_ok() -> bool:
    """True when PyTorch can see at least one CUDA device."""
    if not torch.cuda.is_available():
        return False
    try:
        return torch.cuda.device_count() > 0
    except Exception:
        return False


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

    try:
        result = subprocess.run(
            ['nvidia-smi'],
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

    cuda_available = _cuda_runtime_ok()
    cuda_device_count = 0
    if cuda_available:
        try:
            cuda_device_count = torch.cuda.device_count()
        except Exception:
            cuda_device_count = 0

    # Extract information from the output
    virtual_memory = psutil.virtual_memory()._asdict()
    swap_memory = psutil.swap_memory()._asdict()
    disk_usages = disk_usage('/')._asdict()

    sys_info = {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": psutil.cpu_count(logical=False),
        "cpu_percent": f"{psutil.cpu_percent(interval=1)} %",

        "nvidia_smi_version": nvidia_info["nvidia_smi_version"],
        "driver_version": nvidia_info["driver_version"],
        "cuda_version": nvidia_info["cuda_version"],
        "gpu_name": nvidia_info["gpu_name"],
        "cuda_device_count": cuda_device_count,
        "py_torch_cuda_available": "Yes" if cuda_available else None,
        "py_torch_cuda_version": torch.version.cuda or None,
        "py_torch_version": torch.__version__,

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

    Returns:
        None
    """
    sys_info = get_system_info()

    def colored_value(value):
        if value == "N/A":
            return colored_text(value, 'red')
        else:
            return colored_text(value, 'green')

    # Print the extracted values
    pr_color(f' * NVIDIA-SMI Version: {colored_value(sys_info["nvidia_smi_version"] or "N/A")}',
             'yellow')
    pr_color(f' * Driver Version: {colored_value(sys_info["driver_version"] or "N/A")}', 'yellow')
    pr_color(f' * CUDA Version: {colored_value(sys_info["cuda_version"] or "N/A")}', 'yellow')

    if sys_info["gpu_name"]:
        pr_color(f' * GPU: {colored_value(sys_info["gpu_name"])}', 'yellow')

    # Check CUDA availability using PyTorch
    pr_color(f' * PyTorch CUDA Available: {colored_value(sys_info["py_torch_cuda_available"] or "N/A")}', 'yellow')
    if sys_info["cuda_device_count"]:
        pr_color(
            f' * CUDA Devices: {colored_value(str(sys_info["cuda_device_count"]))}',
            'yellow',
        )
    pr_color(f' * PyTorch CUDA Version: {colored_value(sys_info["py_torch_cuda_version"] or "N/A")}', 'yellow')

    # Check PyTorch version
    pr_color(f' * PyTorch Version: {colored_value(sys_info["py_torch_version"] or "N/A")}', 'yellow')

    cuda_ready = bool(sys_info["py_torch_cuda_available"])
    driver_reported = bool(sys_info["driver_version"] or sys_info["nvidia_smi_version"])
    cuda_reported = bool(sys_info["cuda_version"] or sys_info["py_torch_cuda_version"])

    # Functional CUDA test wins; parsing tolerates driver 6xx header renames.
    if cuda_ready and driver_reported and cuda_reported and sys_info["py_torch_version"]:
        print(f'{colored_text(" * System Check Result:", "yellow")} {colored_text("PASSED", "green")}')
    else:
        print(f'{colored_text(" * System Check Result:", "yellow")} {colored_text("FAILED", "red")}')
