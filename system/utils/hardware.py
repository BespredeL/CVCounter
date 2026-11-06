# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

"""
Hardware probing shared by the CLI installer (install.py) and the web runtime installer.

Standard library only: install.py imports this module before any project dependency exists.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional

PYTORCH_INDEX_BASE = "https://download.pytorch.org/whl"

# RTX 50xx / Blackwell silicon needs CUDA 12.8 wheels; older builds have no matching binaries.
_BLACKWELL_MARKERS = ("5070", "5080", "5090", "5060", "blackwell", "sm_120", "b100", "b200")

# Turing (sm_75) is the oldest architecture shipped in the cu128/cu130 wheels: PyTorch dropped
# Maxwell, Pascal and Volta from those builds. The cu124/cu118 indexes still carry them, but stop
# at torch 2.6.0, so the last supported release is pinned explicitly instead of trusting the ceiling.
_TURING_COMPUTE_CAP = 7.5
_PRE_TURING_PACKAGES = ('torch<=2.6', 'torchvision<=0.21')
_PRE_TURING_NOTE = (
    "PyTorch 2.7 and newer official wheels have no kernels for this GPU architecture; "
    "the installer pins torch to 2.6. Use ONNX Runtime for newer models."
)

NVIDIA_DRIVER_NOTE = (
    "No reachable NVIDIA driver: a CUDA build would not start, so the CPU build is installed. "
    "Install or update the official graphics driver to get GPU acceleration."
)


def _pytorch_build(index: str, label: str, *, force_reinstall: bool = True,
                   packages: Optional[tuple] = None, note: Optional[str] = None) -> Dict[str, Any]:
    """One candidate wheel source plus the pip arguments and caveat text that go with it."""
    build: Dict[str, Any] = {
        'index_url': f"{PYTORCH_INDEX_BASE}/{index}",
        'label': label,
        'force_reinstall': force_reinstall,
    }
    if packages:
        build['packages'] = list(packages)
    if note:
        build['note'] = note
    return build


def detect_nvidia_compute_cap() -> Optional[float]:
    """Read the GPU compute capability (major.minor, as CUDA reports sm_XX) straight from nvidia-smi."""
    nvidia_smi_cmd = find_nvidia_smi()
    if not nvidia_smi_cmd:
        return None
    try:
        res = subprocess.run(
            [nvidia_smi_cmd, "--query-gpu=compute_cap", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=6,
            check=False,
        )
        if res.returncode != 0:
            return None
        for line in res.stdout.splitlines():
            try:
                return float(line.strip())
            except ValueError:
                continue
    except Exception:
        pass
    return None


def compute_cap_to_sm(compute_cap: Optional[float]) -> Optional[str]:
    """Format a compute capability as the sm_XX label used by CUDA tooling (8.6 -> sm_86, 12.0 -> sm_120)."""
    if compute_cap is None:
        return None
    major, _, minor = str(compute_cap).partition('.')
    return f"sm_{major}{(minor[:1] or '0')}"



def find_nvidia_smi() -> Optional[str]:
    """Locate the nvidia-smi executable in PATH, System32, NVSMI or the Windows DriverStore."""
    nvidia_smi_cmd = shutil.which("nvidia-smi")
    if nvidia_smi_cmd or sys.platform != "win32":
        return nvidia_smi_cmd

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
        except OSError:
            pass

    for possible_path in candidates:
        if os.path.exists(possible_path):
            return possible_path
    return None


def detect_nvidia_gpu() -> Dict[str, Any]:
    """Detect NVIDIA GPU, driver version, and supported CUDA version."""
    info: Dict[str, Any] = {
        "available": False,
        "name": None,
        "driver_version": None,
        "cuda_max": None,
    }

    nvidia_smi_cmd = find_nvidia_smi()
    if not nvidia_smi_cmd:
        return info

    try:
        res = subprocess.run(
            [nvidia_smi_cmd],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        if res.returncode == 0 and res.stdout:
            info["available"] = True
            merged = res.stdout.replace('\n', ' ')

            m_drv = re.search(r'(?:Driver Version|KMD Version):\s*([\d.]+)', merged, re.I)
            if m_drv:
                info["driver_version"] = m_drv.group(1)

            m_cuda = re.search(r'CUDA(?: UMD)? Version:\s*([\d.]+)', merged, re.I)
            if m_cuda:
                info["cuda_max"] = m_cuda.group(1)

            name_res = subprocess.run(
                [nvidia_smi_cmd, "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if name_res.returncode == 0 and name_res.stdout.strip():
                info["name"] = name_res.stdout.strip().splitlines()[0]
            else:
                info["name"] = "NVIDIA GeForce / RTX GPU"
    except Exception:
        pass

    return info


def detect_all_gpus() -> List[str]:
    """Retrieve list of all video adapters in the system."""
    gpus: List[str] = []
    if sys.platform == "win32":
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if res.returncode == 0:
                gpus = [line.strip() for line in res.stdout.splitlines() if line.strip()]
        except Exception:
            pass
    elif sys.platform.startswith("linux"):
        try:
            res = subprocess.run(
                ["lspci"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    if any(k in line.lower() for k in ["vga", "3d", "display"]):
                        gpus.append(line.strip())
        except Exception:
            pass
    return gpus


def detect_hardware_profile(force_profile: Optional[str] = None) -> Dict[str, Any]:
    """Analyze hardware and select optimal acceleration profile."""
    if force_profile:
        return {"profile": force_profile, "name": f"User specified ({force_profile})"}

    nv = detect_nvidia_gpu()
    all_gpus = detect_all_gpus()
    all_gpus_str = " ".join(all_gpus).lower()

    if nv["available"]:
        driver = nv.get("driver_version")
        cuda = nv.get("cuda_max")
        cuda_major = 12.0
        if cuda:
            try:
                cuda_major = float(cuda.split()[0])
            except (ValueError, IndexError):
                cuda_major = 12.0

        return {
            "profile": "nvidia_cuda",
            "name": nv["name"] or "NVIDIA GPU",
            "driver_version": driver,
            "cuda_version": cuda,
            "cuda_major": cuda_major,
            "compute_cap": detect_nvidia_compute_cap(),
            "all_gpus": all_gpus,
        }

    # Fallback NVIDIA check via adapter list (e.g., Windows Sandbox, VM, minimal DCH)
    if any(k in all_gpus_str for k in ["nvidia", "geforce", "rtx", "gtx", "quadro", "tesla"]):
        nv_name = next((g for g in all_gpus if
                        any(k in g.lower() for k in ["nvidia", "geforce", "rtx", "gtx", "quadro", "tesla"])),
                       "NVIDIA GeForce GPU")
        return {
            "profile": "nvidia_cuda",
            "name": nv_name,
            "driver_version": "NVIDIA Windows Driver",
            "cuda_version": "12.x",
            "cuda_major": 12.0,
            "compute_cap": None,
            "all_gpus": all_gpus,
            "driver_missing": True,
        }

    if "amd" in all_gpus_str or "radeon" in all_gpus_str:
        amd_name = next((g for g in all_gpus if "amd" in g.lower() or "radeon" in g.lower()), "AMD Radeon GPU")
        # DirectML is a Windows-only execution provider; on Linux an AMD card has no pip-installable
        # accelerator, so it must not be advertised as DirectML.
        return {
            "profile": "amd_directml" if sys.platform == "win32" else "amd",
            "name": amd_name,
            "all_gpus": all_gpus,
        }

    if "intel" in all_gpus_str or "arc" in all_gpus_str:
        intel_name = next((g for g in all_gpus if "intel" in g.lower() or "arc" in g.lower()), "Intel GPU / CPU")
        return {
            "profile": "intel_openvino",
            "name": intel_name,
            "all_gpus": all_gpus,
        }

    return {
        "profile": "cpu",
        "name": "Processor (CPU Inference)",
        "all_gpus": all_gpus,
    }


def is_blackwell_gpu(hw: Dict[str, Any]) -> bool:
    """Return True when the detected adapter belongs to the RTX 50xx / Blackwell family."""
    gpu_name = (hw.get("name") or "").lower()
    return any(marker in gpu_name for marker in _BLACKWELL_MARKERS)


def resolve_pytorch_builds(hw: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Return the PyTorch wheel sources to try, best match first, selected by GPU architecture.

    Compute capability from nvidia-smi decides first, the driver's CUDA level second: Blackwell
    needs cu128 or newer, Turing..Ada follow the driver, and Maxwell/Pascal/Volta exist only in
    the cu124/cu118 wheels and are pinned to the last release that shipped their kernels. With no
    reachable NVIDIA driver a CUDA wheel cannot load at all, so the CPU build is the only honest
    answer there.
    """
    if (hw.get("profile") or "") != "nvidia_cuda":
        return [_pytorch_build("cpu", "CPU", force_reinstall=False)]

    if hw.get("driver_missing"):
        return [_pytorch_build("cpu", "CPU", force_reinstall=False, note=NVIDIA_DRIVER_NOTE)]

    cap = hw.get("compute_cap")
    if cap is None and is_blackwell_gpu(hw):
        cap = 12.0

    cuda_major = hw.get("cuda_major", 12.0)

    if cap is not None and cap < _TURING_COMPUTE_CAP:
        pre_turing = [_pytorch_build("cu118", "CUDA 11.8 (torch 2.6)",
                                     packages=_PRE_TURING_PACKAGES, note=_PRE_TURING_NOTE)]
        if cuda_major >= 12.4:
            pre_turing.insert(0, _pytorch_build("cu124", "CUDA 12.4 (torch 2.6)",
                                                packages=_PRE_TURING_PACKAGES, note=_PRE_TURING_NOTE))
        return pre_turing

    if cuda_major >= 13.0:
        return [
            _pytorch_build("cu130", "CUDA 13.0"),
            _pytorch_build("cu128", "CUDA 12.8"),
        ]

    if cuda_major >= 12.0:
        if is_blackwell_gpu(hw) or (cap or 0.0) >= 12.0:
            return [_pytorch_build("cu128", "CUDA 12.8")]
        return [_pytorch_build("cu128", "CUDA 12.8"), _pytorch_build("cu124", "CUDA 12.4")]

    return [_pytorch_build("cu118", "CUDA 11.8")]
