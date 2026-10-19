# -*- coding: utf-8 -*-
"""
CVCounter - Universal automated system installer.
Automatically detects available hardware (NVIDIA GPU, AMD GPU, Intel GPU/CPU)
and installs all required dependencies for maximum hardware acceleration.
"""

import os
import sys
import platform
import subprocess
import shutil
import re
import argparse
from pathlib import Path


# Configure Windows console for correct font and encoding handling
def setup_windows_console():
    """Configure Windows console code pages and Python streams for UTF-8 output."""
    if sys.platform != "win32":
        return

    import ctypes
    kernel32 = ctypes.windll.kernel32

    # UTF-8 console code pages. install.bat also sets PYTHONUTF8 and PYTHONIOENCODING.
    try:
        kernel32.SetConsoleOutputCP(65001)
        kernel32.SetConsoleCP(65001)
    except Exception:
        pass

    # Reconfigure Python output streams so text is emitted as UTF-8.
    for stream_name in ("stdout", "stderr", "stdin"):
        stream = getattr(sys, stream_name, None)
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


setup_windows_console()


# Console color styling
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

    @classmethod
    def disable(cls):
        cls.HEADER = ''
        cls.BLUE = ''
        cls.CYAN = ''
        cls.GREEN = ''
        cls.YELLOW = ''
        cls.RED = ''
        cls.RESET = ''
        cls.BOLD = ''


# Enable ANSI escape sequence support in Windows 10+ cmd
if sys.platform == "win32" and "WT_SESSION" not in os.environ and "TERM" not in os.environ:
    os.system("")


def pr(text: str, color: str = '', bold: bool = False):
    prefix = f"{Colors.BOLD if bold else ''}{color}"
    suffix = Colors.RESET if (color or bold) else ''
    print(f"{prefix}{text}{suffix}", flush=True)


def pr_step(step: int, total: int, title: str):
    print(flush=True)
    pr(f"[{step}/{total}] {title}", Colors.CYAN, bold=True)
    pr("-" * 60, Colors.CYAN)


def pr_ok(text: str):
    pr(f"  [OK] {text}", Colors.GREEN)


def pr_info(text: str):
    pr(f"  [i]  {text}", Colors.BLUE)


def pr_warn(text: str):
    pr(f"  [!]  {text}", Colors.YELLOW, bold=True)


def pr_err(text: str):
    pr(f"  [X]  {text}", Colors.RED, bold=True)


ROOT_DIR = Path(__file__).resolve().parent
REQUIREMENTS_CORE = ROOT_DIR / "requirements.txt"
REQUIREMENTS_ULTRALYTICS = ROOT_DIR / "requirements-ultralytics.txt"
REQUIREMENTS_OPENVINO = ROOT_DIR / "requirements-openvino.txt"
CONFIG_EXAMPLE = ROOT_DIR / "config" / "config.example.json"
CONFIG_FILE = ROOT_DIR / "config" / "config.json"


# --------------------------------------------------------------------------------
# System components (Visual C++ Redistributable)
# --------------------------------------------------------------------------------

def ensure_vcredist() -> bool:
    """Check and automatically install Microsoft Visual C++ 2015-2022 Redistributable (x64)."""
    if sys.platform != "win32":
        return True

    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    vc_dll = os.path.join(system_root, "System32", "vcruntime140_1.dll")
    if os.path.exists(vc_dll):
        pr_ok("Microsoft Visual C++ 2015-2022 Redistributable (x64) is installed")
        return True

    pr_warn("Microsoft Visual C++ 2015-2022 Redistributable (x64) not found!")
    pr_info("It is required for PyTorch (c10.dll) and ONNX Runtime.")
    pr_info("Starting automatic download and installation of vc_redist.x64.exe...")

    url = "https://aka.ms/vs/17/release/vc_redist.x64.exe"
    temp_dir = Path(os.environ.get("TEMP", "."))
    installer_path = temp_dir / "vc_redist.x64.exe"

    downloaded = False
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=40) as response, open(installer_path, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
        if installer_path.exists() and installer_path.stat().st_size > 5_000_000:
            downloaded = True
    except Exception as e:
        pr_warn(f"Download via urllib failed ({e}), trying curl...")

    if not downloaded:
        try:
            res = subprocess.run(["curl.exe", "-fSLo", str(installer_path), url], timeout=60, check=False)
            if res.returncode == 0 and installer_path.exists() and installer_path.stat().st_size > 5_000_000:
                downloaded = True
        except Exception:
            pass

    if downloaded:
        try:
            pr_info("Installing Visual C++ Redistributable in silent mode...")
            subprocess.run([str(installer_path), "/install", "/quiet", "/norestart"], timeout=120, check=False)
            if not os.path.exists(vc_dll):
                pr_info("Requesting administrator approval (UAC) to install...")
                subprocess.run([str(installer_path), "/install", "/norestart"], timeout=180, check=False)

            if installer_path.exists():
                try:
                    installer_path.unlink()
                except Exception:
                    pass

            if os.path.exists(vc_dll):
                pr_ok("Microsoft Visual C++ Redistributable (x64) installed successfully!")
                return True
        except Exception as e:
            pr_err(f"Error running Visual C++ installer: {e}")

    pr_err("Failed to automatically install Visual C++ Redistributable.")
    pr_info("Please install it manually: https://aka.ms/vs/17/release/vc_redist.x64.exe")
    return False


# --------------------------------------------------------------------------------
# Hardware detection (GPU / CPU / OS)
# --------------------------------------------------------------------------------

def detect_nvidia_gpu() -> dict:
    """Detect NVIDIA GPU, driver version, and supported CUDA version."""
    info = {
        "available": False,
        "name": None,
        "driver_version": None,
        "cuda_max": None,
    }

    # Search for nvidia-smi in PATH, System32, NVSMI, and DriverStore (Windows DCH)
    nvidia_smi_cmd = shutil.which("nvidia-smi")
    if not nvidia_smi_cmd and sys.platform == "win32":
        candidates = [
            r"C:\Windows\System32\nvidia-smi.exe",
            r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
            r"C:\Windows\SysWOW64\nvidia-smi.exe",
        ]
        # Search Windows DriverStore repository
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
            if os.path.exists(possible_path):
                nvidia_smi_cmd = possible_path
                break

    if nvidia_smi_cmd:
        try:
            res = subprocess.run(
                [nvidia_smi_cmd],
                capture_output=True,
                text=True,
                timeout=8,
                check=False
            )
            if res.returncode == 0 and res.stdout:
                info["available"] = True
                merged = res.stdout.replace('\n', ' ')

                # Extract driver and CUDA versions
                m_drv = re.search(r'(?:Driver Version|KMD Version):\s*([\d.]+)', merged, re.I)
                if m_drv:
                    info["driver_version"] = m_drv.group(1)

                m_cuda = re.search(r'CUDA(?: UMD)? Version:\s*([\d.]+)', merged, re.I)
                if m_cuda:
                    info["cuda_max"] = m_cuda.group(1)

                # Query exact GPU model name
                name_res = subprocess.run(
                    [nvidia_smi_cmd, "--query-gpu=name", "--format=csv,noheader"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False
                )
                if name_res.returncode == 0 and name_res.stdout.strip():
                    info["name"] = name_res.stdout.strip().splitlines()[0]
                else:
                    info["name"] = "NVIDIA GeForce / RTX GPU"
        except Exception:
            pass

    return info


def detect_all_gpus() -> list[str]:
    """Retrieve list of all video adapters in the system."""
    gpus = []
    if sys.platform == "win32":
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False
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
                check=False
            )
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    if any(k in line.lower() for k in ["vga", "3d", "display"]):
                        gpus.append(line.strip())
        except Exception:
            pass
    return gpus


def detect_hardware_profile(force_profile: str = None) -> dict:
    """Analyze hardware and select optimal acceleration profile."""
    if force_profile:
        return {"profile": force_profile, "name": f"User specified ({force_profile})"}

    nv = detect_nvidia_gpu()
    all_gpus = detect_all_gpus()
    all_gpus_str = " ".join(all_gpus).lower()

    if nv["available"]:
        driver = nv.get("driver_version")
        cuda = nv.get("cuda_max")
        # Analyze supported CUDA version
        cuda_major = 12.0
        if cuda:
            try:
                cuda_major = float(cuda.split()[0])
            except Exception:
                cuda_major = 12.0

        return {
            "profile": "nvidia_cuda",
            "name": nv["name"] or "NVIDIA GPU",
            "driver_version": driver,
            "cuda_version": cuda,
            "cuda_major": cuda_major,
            "all_gpus": all_gpus
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
            "all_gpus": all_gpus,
            "driver_missing": True,
        }

    # Check AMD Radeon
    if "amd" in all_gpus_str or "radeon" in all_gpus_str:
        amd_name = next((g for g in all_gpus if "amd" in g.lower() or "radeon" in g.lower()), "AMD Radeon GPU")
        return {
            "profile": "amd_directml",
            "name": amd_name,
            "all_gpus": all_gpus
        }

    # Check Intel Arc / Iris Xe / Intel CPU
    if "intel" in all_gpus_str or "arc" in all_gpus_str:
        intel_name = next((g for g in all_gpus if "intel" in g.lower() or "arc" in g.lower()), "Intel GPU / CPU")
        return {
            "profile": "intel_openvino",
            "name": intel_name,
            "all_gpus": all_gpus
        }

    # CPU only
    return {
        "profile": "cpu",
        "name": "Processor (CPU Inference)",
        "all_gpus": all_gpus
    }


def prompt_nvidia_driver_guidance(hw: dict):
    """Guide the user when an NVIDIA GPU is detected but official driver or CUDA is missing."""
    print()
    pr_warn("NVIDIA GPU detected, but NVIDIA Display Driver / CUDA runtime was not found!")
    pr_info("PyTorch requires an official NVIDIA graphics driver to enable GPU hardware acceleration.")
    pr_info("NOTE: Installing the full CUDA Toolkit (3+ GB) is NOT required.")
    pr_info("Only the standard NVIDIA graphics driver (Game Ready or Studio) is needed.")
    pr_info("-> Download official drivers: https://www.nvidia.com/Download/index.aspx")
    if sys.platform == "win32" and shutil.which("winget"):
        pr_info("-> Quick install command: winget install --id Nvidia.GraphicsDriver")

    if sys.stdin and sys.stdin.isatty():
        try:
            choice = input("\n  Open NVIDIA driver download page in your browser now? [Y/n]: ").strip().lower()
            if choice in ("", "y", "yes"):
                import webbrowser
                webbrowser.open("https://www.nvidia.com/Download/index.aspx")
        except Exception:
            pass
    print()


# --------------------------------------------------------------------------------
# Utilities for running pip and managing packages
# --------------------------------------------------------------------------------

def sanitize_pip_config():
    """Remove outdated/unreachable repositories (e.g. pypi.ngc.nvidia.com) from pip config."""
    ini_candidates = [
        r"C:\ProgramData\pip\pip.ini",
        os.path.expanduser("~/pip/pip.ini"),
        os.path.expandvars(r"%APPDATA%\pip\pip.ini") if sys.platform == "win32" else "",
    ]
    for ini_path in ini_candidates:
        if ini_path and os.path.exists(ini_path):
            try:
                with open(ini_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                if any("pypi.ngc.nvidia.com" in l for l in lines):
                    pr_info(f"Cleaning outdated NVIDIA index from {ini_path}...")
                    new_lines = [l for l in lines if
                                 "pypi.ngc.nvidia.com" not in l and "extra-index-url" not in l and "trusted-host" not in l]
                    with open(ini_path, "w", encoding="utf-8") as f:
                        f.writelines(new_lines)
            except Exception:
                pass


def run_pip(args: list[str], description: str = "") -> bool:
    """Run pip command in the current Python environment."""
    cmd = [sys.executable, "-m", "pip"] + args
    if description:
        pr_info(f"{description}...")
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        for line in proc.stdout:
            line_str = line.strip()
            # Filter verbose spam, show only significant lines
            if any(k in line_str.lower() for k in
                   ["collecting", "downloading", "installing", "successfully installed", "error", "warning"]):
                print(f"    {line_str}", flush=True)
        proc.wait()
        return proc.returncode == 0
    except Exception as e:
        pr_err(f"Error executing pip: {e}")
        return False


def is_package_installed(pkg_name: str) -> bool:
    """Check if a package is installed in the current environment."""
    try:
        import importlib.metadata
        importlib.metadata.version(pkg_name)
        return True
    except Exception:
        pass
    try:
        import pkg_resources
        pkg_resources.get_distribution(pkg_name)
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------------
# Installation process
# --------------------------------------------------------------------------------

def check_python_compatibility():
    """Verify Python version compatibility and environment isolation."""
    major, minor = sys.version_info[:2]
    pr_info(f"Current Python version: {sys.version.split()[0]} ({sys.executable})")

    in_venv = sys.prefix != sys.base_prefix
    if in_venv:
        pr_ok(f"Isolated virtual environment: active ({sys.prefix})")
    else:
        pr_warn("Warning: script is running outside an isolated virtual environment (running via install.bat is recommended)")

    if (major, minor) < (3, 10):
        pr_warn(f"Python {major}.{minor} might be outdated. Python 3.11 is recommended for neural networks.")
    elif (major, minor) > (3, 12):
        pr_warn(
            f"Python {major}.{minor} is a very recent version. Compiled wheels for some libraries (ONNX Runtime / PyTorch) might be missing.")
        pr_warn("If you encounter errors, using Python 3.11 is recommended.")
    else:
        pr_ok(f"Python version {major}.{minor} is well-suited for neural networks!")


def check_torch_cuda_compatibility(hw: dict) -> tuple[bool, str]:
    """Check if installed PyTorch supports the detected GPU."""
    try:
        import torch
        if not torch.cuda.is_available():
            return False, "CUDA is not available in the installed PyTorch package"

        cap = torch.cuda.get_device_capability()
        target_sm = f"sm_{cap[0]}{cap[1]}"
        archs = torch.cuda.get_arch_list()

        # For Blackwell (RTX 50-series: 5070 / 5080 / 5090 - sm_120, sm_100)
        if cap[0] >= 12 and target_sm not in archs:
            return False, f"Architecture {target_sm} ({hw.get('name', 'GPU')}) is not supported by installed PyTorch (requires CUDA 12.8+)"

        # Fast test tensor allocation on CUDA to confirm no driver/kernel errors
        t = torch.zeros(1, device='cuda')
        del t
        return True, f"{torch.__version__} (CUDA {torch.version.cuda}, {target_sm})"
    except Exception as e:
        return False, str(e)


def install_hardware_pytorch(hw: dict, reinstall: bool = False) -> bool:
    """Install hardware-accelerated PyTorch and TorchVision."""
    profile = hw["profile"]

    if not reinstall and is_package_installed("torch"):
        if profile == "nvidia_cuda":
            compatible, desc = check_torch_cuda_compatibility(hw)
            if compatible:
                pr_ok(f"PyTorch is already installed and fully compatible with GPU: {desc}")
                return True
            else:
                pr_warn(f"Installed PyTorch is incompatible with current GPU: {desc}")
                pr_info("Uninstalling incompatible PyTorch build...")
                run_pip(["uninstall", "-y", "torch", "torchvision"])
        else:
            pr_ok("PyTorch is already installed.")
            return True

    pr_info("Selecting optimal PyTorch build...")

    if profile == "nvidia_cuda":
        cuda_major = hw.get("cuda_major", 12)
        gpu_name = hw.get("name", "").lower()
        is_blackwell = any(
            k in gpu_name for k in ["5070", "5080", "5090", "5060", "blackwell", "sm_120", "b100", "b200"])

        if is_blackwell or cuda_major >= 12.0:
            pr_info(
                f"Detected NVIDIA GPU ({hw.get('name')}) -> Installing PyTorch with CUDA 12.8+ support (RTX 50xx Blackwell / Ada / Ampere)...")
            cmd = ["install", "--force-reinstall", "torch", "torchvision", "--index-url",
                   "https://download.pytorch.org/whl/cu128"]
            success = run_pip(cmd, "Installing PyTorch and TorchVision (CUDA 12.8)")
            if not success and not is_blackwell:
                pr_warn("Failed to install PyTorch via cu128. Trying cu124...")
                cmd = ["install", "--force-reinstall", "torch", "torchvision", "--index-url",
                       "https://download.pytorch.org/whl/cu124"]
                success = run_pip(cmd, "Installing PyTorch and TorchVision (CUDA 12.4)")
        else:
            pr_info("Installing PyTorch for CUDA 11.8...")
            cmd = ["install", "--force-reinstall", "torch", "torchvision", "--index-url",
                   "https://download.pytorch.org/whl/cu118"]
            success = run_pip(cmd, "Installing PyTorch and TorchVision (CUDA 11.8)")
    else:
        pr_info("Installing lightweight CPU version of PyTorch...")
        cmd = ["install", "torch", "torchvision", "--index-url", "https://download.pytorch.org/whl/cpu"]
        success = run_pip(cmd, "Installing PyTorch and TorchVision")

    if not success and profile == "nvidia_cuda":
        pr_warn("Trying universal PyTorch installation...")
        cmd_fallback = ["install", "torch", "torchvision"]
        success = run_pip(cmd_fallback, "Fallback PyTorch installation")

    return success


def install_inference_backend(hw: dict) -> bool:
    """Install inference backend (ONNX Runtime GPU / DirectML / CPU / OpenVINO)."""
    profile = hw["profile"]

    if profile == "nvidia_cuda":
        pr_info("Configuring ONNX Runtime hardware acceleration for NVIDIA GPU...")
        # Remove CPU onnxruntime to prevent conflicts
        if is_package_installed("onnxruntime"):
            pr_info("Removing CPU 'onnxruntime' package to prevent conflicts...")
            run_pip(["uninstall", "-y", "onnxruntime"])
        success = run_pip(["install", "onnxruntime-gpu"], "Installing onnxruntime-gpu")
        return success

    elif profile == "amd_directml":
        pr_info("Configuring DirectML acceleration for AMD Radeon...")
        if is_package_installed("onnxruntime"):
            run_pip(["uninstall", "-y", "onnxruntime"])
        success = run_pip(["install", "onnxruntime-directml"], "Installing onnxruntime-directml")
        return success

    elif profile == "intel_openvino":
        pr_info("Configuring Intel OpenVINO hardware acceleration...")
        run_pip(["install", "-r", str(REQUIREMENTS_OPENVINO)], "Installing OpenVINO")
        success = run_pip(["install", "onnxruntime"], "Installing onnxruntime")
        return success

    else:
        pr_info("Configuring CPU inference...")
        success = run_pip(["install", "onnxruntime"], "Installing onnxruntime")
        return success


def install_core_dependencies(hw: dict) -> bool:
    """Install dependencies from requirements.txt without GPU package conflicts."""
    if not REQUIREMENTS_CORE.exists():
        pr_err(f"File {REQUIREMENTS_CORE} not found!")
        return False

    pr_info("Installing core system packages...")

    # Read requirements.txt and filter out onnxruntime if GPU runtime is installed
    lines_to_install = []
    with open(REQUIREMENTS_CORE, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            # Skip onnxruntime on GPU profiles to avoid overwriting onnxruntime-gpu/directml
            if hw["profile"] in ["nvidia_cuda", "amd_directml"] and stripped.startswith("onnxruntime"):
                continue
            # Skip legacy TensorRT packages
            if stripped.startswith("tensorrt") or stripped.startswith("nvidia-pyindex"):
                continue
            lines_to_install.append(stripped)

    # Create temporary requirements file
    temp_req = ROOT_DIR / ".temp_requirements.txt"
    try:
        with open(temp_req, "w", encoding="utf-8") as f:
            f.write("\n".join(lines_to_install) + "\n")

        success = run_pip(["install", "-r", str(temp_req)], "Installing core libraries")
    finally:
        if temp_req.exists():
            try:
                temp_req.unlink()
            except Exception:
                pass

    return success


def install_ultralytics() -> bool:
    """Install Ultralytics YOLO for detection, annotation, and training."""
    if not REQUIREMENTS_ULTRALYTICS.exists():
        pr_err(f"File {REQUIREMENTS_ULTRALYTICS} not found!")
        return False

    pr_info("Installing Ultralytics YOLO (support for .pt models, tracking, and training)...")
    return run_pip(["install", "-r", str(REQUIREMENTS_ULTRALYTICS)], "Installing Ultralytics YOLO")


def setup_configuration_and_storage(hw: dict):
    """Initialize config/config.json and required storage directories."""
    pr_info("Checking configuration files and storage directories...")

    # Create required directories
    directories = [
        ROOT_DIR / "storage" / "datasets",
        ROOT_DIR / "storage" / "media" / "captures",
        ROOT_DIR / "storage" / "media" / "records",
        ROOT_DIR / "storage" / "logs",
        ROOT_DIR / "config" / "ultralytics" / "models",
    ]
    for d in directories:
        d.mkdir(parents=True, exist_ok=True)
    pr_ok("Storage folders ready (storage/datasets, storage/media, storage/logs)")

    # Check config.json
    if not CONFIG_FILE.exists():
        if CONFIG_EXAMPLE.exists():
            shutil.copyfile(CONFIG_EXAMPLE, CONFIG_FILE)
            pr_ok("Created initial config file config/config.json from template")
        else:
            pr_warn("Template config.example.json not found, please create config.json manually.")
    else:
        pr_ok("Configuration file config/config.json already exists")


# --------------------------------------------------------------------------------
# Diagnostics and post-installation verification
# --------------------------------------------------------------------------------

def verify_installation(hw: dict) -> bool:
    """Comprehensive health check of installed components."""
    print()
    pr("============================================================", Colors.CYAN, bold=True)
    pr("          FINAL SYSTEM INSTALLATION DIAGNOSTICS", Colors.CYAN, bold=True)
    pr("============================================================", Colors.CYAN, bold=True)

    all_ok = True

    # 1. Check PyTorch and CUDA
    try:
        import torch
        torch_ver = torch.__version__
        cuda_ok = torch.cuda.is_available()
        cuda_count = torch.cuda.device_count() if cuda_ok else 0
        device_name = torch.cuda.get_device_name(0) if cuda_ok and cuda_count > 0 else "CPU"

        if hw["profile"] == "nvidia_cuda":
            if cuda_ok:
                compatible, desc = check_torch_cuda_compatibility(hw)
                if not compatible:
                    pr(f"  [!] PyTorch: {torch_ver} | GPU {device_name} is not supported by current build!",
                       Colors.YELLOW, bold=True)
                    pr(f"      Reason: {desc}", Colors.YELLOW)
                    pr("      Recommended: pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128",
                       Colors.YELLOW)
                    all_ok = False
                else:
                    pr(f"  [OK] PyTorch: {torch_ver} | CUDA Active: YES ({device_name})", Colors.GREEN)
            else:
                pr(f"  [!] PyTorch: {torch_ver} | CUDA: No access to GPU", Colors.YELLOW, bold=True)
                pr("      Reason: Official NVIDIA driver is missing, outdated, or system restart required.", Colors.YELLOW)
                pr("      NOTE: CUDA Toolkit (3+ GB) is NOT required. Only the official graphics driver is needed.", Colors.YELLOW)
                pr("      Download driver: https://www.nvidia.com/Download/index.aspx", Colors.CYAN)
                if sys.platform == "win32" and shutil.which("winget"):
                    pr("      Quick install command: winget install --id Nvidia.GraphicsDriver", Colors.CYAN)
                if sys.stdin and sys.stdin.isatty():
                    try:
                        choice = input("      Open NVIDIA driver download page in browser? [y/N]: ").strip().lower()
                        if choice in ("y", "yes"):
                            import webbrowser
                            webbrowser.open("https://www.nvidia.com/Download/index.aspx")
                    except Exception:
                        pass
                all_ok = False
        else:
            pr(f"  [OK] PyTorch: {torch_ver} (Mode: {device_name})", Colors.GREEN)
    except Exception as e:
        err_str = str(e)
        pr(f"  [ERROR] PyTorch: {e}", Colors.RED)
        if "126" in err_str or "c10.dll" in err_str or "vcruntime" in err_str.lower():
            pr_warn("       -> Reason: Microsoft Visual C++ 2015-2022 Redistributable (x64) is missing!")
            pr_info("       -> Download link: https://aka.ms/vs/17/release/vc_redist.x64.exe")
        all_ok = False

    # 2. Check ONNX Runtime
    try:
        import onnxruntime as ort
        providers = ort.get_available_providers()
        prov_str = ", ".join(providers)
        if "CUDAExecutionProvider" in providers:
            pr(f"  [OK] ONNX Runtime: {ort.__version__} | Accelerator: CUDAExecutionProvider ({prov_str})", Colors.GREEN)
        elif "DmlExecutionProvider" in providers:
            pr(f"  [OK] ONNX Runtime: {ort.__version__} | Accelerator: DirectML ({prov_str})", Colors.GREEN)
        elif "OpenVINOExecutionProvider" in providers:
            pr(f"  [OK] ONNX Runtime: {ort.__version__} | Accelerator: OpenVINO ({prov_str})", Colors.GREEN)
        else:
            pr(f"  [OK] ONNX Runtime: {ort.__version__} | Providers: {prov_str}", Colors.GREEN)
    except Exception as e:
        err_str = str(e)
        pr(f"  [ERROR] ONNX Runtime: {e}", Colors.RED)
        if "126" in err_str or "onnxruntime_pybind11_state" in err_str:
            pr_warn("       -> Reason: Microsoft Visual C++ 2015-2022 Redistributable (x64) is missing!")
            pr_info("       -> Download link: https://aka.ms/vs/17/release/vc_redist.x64.exe")
        all_ok = False

    # 3. Check OpenCV
    try:
        import cv2
        pr(f"  [OK] OpenCV: {cv2.__version__}", Colors.GREEN)
    except Exception as e:
        pr(f"  [ERROR] OpenCV: {e}", Colors.RED)
        all_ok = False

    # 4. Check Ultralytics YOLO
    try:
        import ultralytics
        pr(f"  [OK] Ultralytics YOLO: {ultralytics.__version__}", Colors.GREEN)
    except Exception as e:
        pr(f"  [ERROR] Ultralytics: {e}", Colors.RED)
        all_ok = False

    # 5. Check Flask and Flask-SocketIO
    try:
        import flask
        import flask_socketio
        import importlib.metadata
        try:
            socketio_ver = importlib.metadata.version('Flask-SocketIO')
        except Exception:
            socketio_ver = getattr(flask_socketio, '__version__', 'OK')
        try:
            flask_ver = importlib.metadata.version('Flask')
        except Exception:
            flask_ver = getattr(flask, '__version__', 'OK')
        pr(f"  [OK] Web Server: Flask {flask_ver}, SocketIO {socketio_ver}", Colors.GREEN)
    except Exception as e:
        pr(f"  [ERROR] Web Server: {e}", Colors.RED)
        all_ok = False

    # 6. Check base detection models
    models_dir = ROOT_DIR / "config" / "ultralytics" / "models"
    available_models = list(models_dir.glob("*.pt")) + list(models_dir.glob("*.onnx"))
    if available_models:
        pr(f"  [OK] Available detection models: {len(available_models)} ({', '.join(m.name for m in available_models[:3])}...)",
           Colors.GREEN)
    else:
        pr("  [INFO] Pre-trained models in config/ultralytics/models will be downloaded automatically on first launch.",
           Colors.BLUE)

    print()
    if all_ok:
        pr("============================================================", Colors.GREEN, bold=True)
        pr("        SYSTEM IS FULLY READY FOR USE! ✓", Colors.GREEN, bold=True)
        pr("============================================================", Colors.GREEN, bold=True)
        print()
        pr("  To launch the system, run:", Colors.CYAN, bold=True)
        if sys.platform == "win32":
            pr("  -> Double-click file: start.bat", Colors.YELLOW, bold=True)
        else:
            pr("  -> ./start.sh  or  venv/bin/python app.py", Colors.YELLOW, bold=True)
        # Get configured host and port from config.json
        web_port = 8080
        web_host = '127.0.0.1'
        if CONFIG_FILE.exists():
            try:
                import json
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg_server = json.load(f).get("server", {})
                    web_port = cfg_server.get("port", 8080)
                    web_host = cfg_server.get("host", "127.0.0.1")
            except Exception:
                pass
        target_ip = '127.0.0.1' if web_host in ('0.0.0.0', '', '::') else web_host
        port_suffix = f":{web_port}" if str(web_port) != "80" else ""

        print()
        pr(f"  Web interface address in browser: http://{target_ip}{port_suffix}", Colors.CYAN)
        pr("  Default credentials: admin / admin (change in settings)", Colors.CYAN)
        print()
    else:
        pr("============================================================", Colors.YELLOW, bold=True)
        pr("  Installation completed with warnings. Please review the messages above.", Colors.YELLOW)
        pr("============================================================", Colors.YELLOW, bold=True)

    return all_ok


# --------------------------------------------------------------------------------
# Main entry point
# --------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Automated CVCounter installer")
    parser.add_argument("--profile", choices=["nvidia_cuda", "amd_directml", "intel_openvino", "cpu"],
                        help="Force specific hardware profile")
    parser.add_argument("--reinstall", action="store_true", help="Reinstall even existing packages")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output")
    args = parser.parse_args()

    if args.no_color:
        Colors.disable()

    print()
    pr("==================================================================", Colors.CYAN, bold=True)
    pr("                CVCounter - AUTOMATIC INSTALLER                  ", Colors.CYAN, bold=True)
    pr("     Intelligent environment and GPU acceleration setup          ", Colors.CYAN)
    pr("==================================================================", Colors.CYAN, bold=True)

    # Step 1: Check Python and system libraries
    pr_step(1, 6, "Checking environment and system libraries")
    check_python_compatibility()
    if sys.platform == "win32":
        ensure_vcredist()

    # Step 2: Hardware and GPU analysis
    pr_step(2, 6, "Detecting GPU and hardware capabilities")
    hw = detect_hardware_profile(args.profile)
    pr(f"  Selected profile: {hw['profile'].upper()}", Colors.BOLD)
    pr(f"  Hardware: {hw['name']}")
    if hw.get("driver_version"):
        pr(f"  Video driver version: {hw['driver_version']}")
    if hw.get("cuda_version"):
        pr(f"  Supported CUDA version: {hw['cuda_version']}")
    if hw.get("all_gpus"):
        pr(f"  All video controllers on system: {', '.join(hw['all_gpus'])}")

    if hw.get("driver_missing"):
        prompt_nvidia_driver_guidance(hw)

    # Step 3: Upgrade pip and build tools
    pr_step(3, 6, "Upgrading pip, setuptools, and wheel")
    sanitize_pip_config()
    run_pip(["install", "--upgrade", "pip", "setuptools", "wheel"], "Upgrading core build tools")

    # Step 4: Install hardware-accelerated PyTorch
    pr_step(4, 6, "Installing hardware-accelerated PyTorch")
    install_hardware_pytorch(hw, reinstall=args.reinstall)

    # Step 5: Install inference backend and project dependencies
    pr_step(5, 6, "Installing ONNX Runtime, Ultralytics, and dependencies")
    install_inference_backend(hw)
    install_core_dependencies(hw)
    install_ultralytics()

    # Step 6: Setup configuration and storage directories
    pr_step(6, 6, "Configuring project settings and storage directories")
    setup_configuration_and_storage(hw)

    # Final verification
    success = verify_installation(hw)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
