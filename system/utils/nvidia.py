# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

import os
import re
import subprocess
from shutil import which


def _find_nvidia_smi() -> str | None:
    """
    Search for nvidia-smi in system PATH, System32, NVSMI, and DriverStore (Windows DCH).

    Returns:
        str | None: Absolute path to nvidia-smi executable or None if not found.
    """
    cmd = which("nvidia-smi")
    if cmd:
        return cmd

    if os.name == "nt":
        candidates = [
            r"C:\Windows\System32\nvidia-smi.exe",
            r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
            r"C:\Windows\SysWOW64\nvidia-smi.exe",
        ]
        ds_root = r"C:\Windows\System32\DriverStore\FileRepository"
        if os.path.isdir(ds_root):
            try:
                for entry in os.scandir(ds_root):
                    if entry.is_dir() and entry.name.lower().startswith("nv"):
                        cand = os.path.join(entry.path, "nvidia-smi.exe")
                        if os.path.isfile(cand):
                            candidates.append(cand)
            except Exception:
                pass

        for possible_path in candidates:
            if os.path.isfile(possible_path):
                return possible_path
    return None


def _nvidia_smi_query(field: str) -> str | None:
    """
    Read one GPU field via the stable nvidia-smi CSV query interface.

    Args:
        field: str - The field to read.

    Returns:
        str | None: The value of the field.
    """
    smi_cmd = _find_nvidia_smi()
    if not smi_cmd:
        return None

    try:
        result = subprocess.run(
            [smi_cmd, f'--query-gpu={field}', '--format=csv,noheader,nounits'],
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

    Args:
        stdout: str - The output of the nvidia-smi command.

    Returns:
        dict[str, str | None]: The parsed information.
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


def _get_torch():
    """Lazily import torch so the application doesn't crash when PyTorch is not installed."""
    try:
        import torch
        return torch
    except (ImportError, Exception):
        return None


def _cuda_runtime_ok() -> bool:
    """
    True when PyTorch can see at least one CUDA device.

    Args:
        None

    Returns:
        bool: True when PyTorch can see at least one CUDA device.
    """
    torch = _get_torch()
    if torch is None:
        return False
    try:
        if not torch.cuda.is_available():
            return False
        return torch.cuda.device_count() > 0
    except Exception:
        return False
