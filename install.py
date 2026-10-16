# -*- coding: utf-8 -*-
"""
CVCounter - Универсальный автоматический установщик системы.
Автоматически определяет доступное оборудование (NVIDIA GPU, AMD GPU, Intel GPU/CPU)
и устанавливает все необходимые зависимости для максимального аппаратного ускорения.
"""

import os
import sys
import platform
import subprocess
import shutil
import re
import argparse
from pathlib import Path

# Настройка консоли Windows для корректного отображения шрифтов и кодировок
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

    # Reconfigure Python output streams so Cyrillic text is emitted as UTF-8.
    for stream_name in ("stdout", "stderr", "stdin"):
        stream = getattr(sys, stream_name, None)
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                if stream_name == "stdin":
                    stream.reconfigure(encoding="utf-8", errors="replace")
                else:
                    stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


setup_windows_console()

# Цветовое оформление консоли
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

# Проверка поддержки ANSI цветов
if sys.platform == "win32" and "WT_SESSION" not in os.environ and "TERM" not in os.environ:
    os.system("")  # Включает поддержку ANSI escape-кодов в Windows 10+ cmd

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
# Системные компоненты (Visual C++ Redistributable)
# --------------------------------------------------------------------------------

def ensure_vcredist() -> bool:
    """Проверка и автоматическая установка Microsoft Visual C++ 2015-2022 Redistributable (x64)."""
    if sys.platform != "win32":
        return True

    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    vc_dll = os.path.join(system_root, "System32", "vcruntime140_1.dll")
    if os.path.exists(vc_dll):
        pr_ok("Microsoft Visual C++ 2015-2022 Redistributable (x64) установлен")
        return True

    pr_warn("Microsoft Visual C++ 2015-2022 Redistributable (x64) не найден!")
    pr_info("Он необходим для запуска PyTorch (c10.dll) и ONNX Runtime.")
    pr_info("Запуск автоматической загрузки и установки vc_redist.x64.exe...")

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
        pr_warn(f"Загрузка через urllib не удалась ({e}), пробуем curl...")

    if not downloaded:
        try:
            res = subprocess.run(["curl.exe", "-fSLo", str(installer_path), url], timeout=60, check=False)
            if res.returncode == 0 and installer_path.exists() and installer_path.stat().st_size > 5_000_000:
                downloaded = True
        except Exception:
            pass

    if downloaded:
        try:
            pr_info("Установка Visual C++ Redistributable в тихом режиме...")
            subprocess.run([str(installer_path), "/install", "/quiet", "/norestart"], timeout=120, check=False)
            if not os.path.exists(vc_dll):
                pr_info("Запрос подтверждения администратора (UAC) для установки...")
                subprocess.run([str(installer_path), "/install", "/norestart"], timeout=180, check=False)

            if installer_path.exists():
                try:
                    installer_path.unlink()
                except Exception:
                    pass

            if os.path.exists(vc_dll):
                pr_ok("Microsoft Visual C++ Redistributable (x64) успешно установлен!")
                return True
        except Exception as e:
            pr_err(f"Ошибка выполнения установщика Visual C++: {e}")

    pr_err("Не удалось автоматически установить Visual C++ Redistributable.")
    pr_info("Пожалуйста, установите его вручную: https://aka.ms/vs/17/release/vc_redist.x64.exe")
    return False


# --------------------------------------------------------------------------------
# Определение оборудования (GPU / CPU / OS)
# --------------------------------------------------------------------------------

def detect_nvidia_gpu() -> dict:
    """Определение видеокарты NVIDIA, версии драйвера и CUDA."""
    info = {
        "available": False,
        "name": None,
        "driver_version": None,
        "cuda_max": None,
    }

    # Поиск nvidia-smi в PATH, System32, NVSMI и DriverStore (Windows DCH)
    nvidia_smi_cmd = shutil.which("nvidia-smi")
    if not nvidia_smi_cmd and sys.platform == "win32":
        candidates = [
            r"C:\Windows\System32\nvidia-smi.exe",
            r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
            r"C:\Windows\SysWOW64\nvidia-smi.exe",
        ]
        # Поиск в каталоге хранилища драйверов Windows (DriverStore)
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

                # Извлечение версии драйвера и CUDA
                m_drv = re.search(r'(?:Driver Version|KMD Version):\s*([\d.]+)', merged, re.I)
                if m_drv:
                    info["driver_version"] = m_drv.group(1)

                m_cuda = re.search(r'CUDA(?: UMD)? Version:\s*([\d.]+)', merged, re.I)
                if m_cuda:
                    info["cuda_max"] = m_cuda.group(1)

                # Запрос точного имени GPU
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
    """Получение списка всех видеоадаптеров в системе."""
    gpus = []
    if sys.platform == "win32":
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"],
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
    """Анализ железа и подбор оптимального профиля ускорения."""
    if force_profile:
        return {"profile": force_profile, "name": f"Пользовательский выбор ({force_profile})"}

    nv = detect_nvidia_gpu()
    all_gpus = detect_all_gpus()
    all_gpus_str = " ".join(all_gpus).lower()

    if nv["available"]:
        driver = nv.get("driver_version")
        cuda = nv.get("cuda_max")
        # Анализ поддерживаемой версии CUDA
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

    # Резервная проверка NVIDIA через список адаптеров (актуально для Windows Sandbox, VM, minimal DCH)
    if any(k in all_gpus_str for k in ["nvidia", "geforce", "rtx", "gtx", "quadro", "tesla"]):
        nv_name = next((g for g in all_gpus if any(k in g.lower() for k in ["nvidia", "geforce", "rtx", "gtx", "quadro", "tesla"])), "NVIDIA GeForce GPU")
        return {
            "profile": "nvidia_cuda",
            "name": nv_name,
            "driver_version": "NVIDIA Windows Driver",
            "cuda_version": "12.x",
            "cuda_major": 12.0,
            "all_gpus": all_gpus
        }

    # Проверка AMD Radeon
    if "amd" in all_gpus_str or "radeon" in all_gpus_str:
        amd_name = next((g for g in all_gpus if "amd" in g.lower() or "radeon" in g.lower()), "AMD Radeon GPU")
        return {
            "profile": "amd_directml",
            "name": amd_name,
            "all_gpus": all_gpus
        }

    # Проверка Intel Arc / Iris Xe / Intel CPU
    if "intel" in all_gpus_str or "arc" in all_gpus_str:
        intel_name = next((g for g in all_gpus if "intel" in g.lower() or "arc" in g.lower()), "Intel GPU / CPU")
        return {
            "profile": "intel_openvino",
            "name": intel_name,
            "all_gpus": all_gpus
        }

    # Только процессор
    return {
        "profile": "cpu",
        "name": "Процессор (CPU Inference)",
        "all_gpus": all_gpus
    }


# --------------------------------------------------------------------------------
# Утилиты запуска pip и пакетов
# --------------------------------------------------------------------------------

def sanitize_pip_config():
    """Удаление устаревших/недоступных репозиториев (например pypi.ngc.nvidia.com) из конфигурации pip."""
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
                    pr_info(f"Очистка устаревшего индекса NVIDIA из {ini_path}...")
                    new_lines = [l for l in lines if "pypi.ngc.nvidia.com" not in l and "extra-index-url" not in l and "trusted-host" not in l]
                    with open(ini_path, "w", encoding="utf-8") as f:
                        f.writelines(new_lines)
            except Exception:
                pass


def run_pip(args: list[str], description: str = "") -> bool:
    """Запуск команды pip в текущем Python окружении."""
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
            # Фильтруем слишком подробный спам, показываем значимые строки
            if any(k in line_str.lower() for k in ["collecting", "downloading", "installing", "successfully installed", "error", "warning"]):
                print(f"    {line_str}", flush=True)
        proc.wait()
        return proc.returncode == 0
    except Exception as e:
        pr_err(f"Ошибка при выполнении pip: {e}")
        return False


def is_package_installed(pkg_name: str) -> bool:
    """Проверка, установлен ли пакет в текущем окружении."""
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
# Процесс установки
# --------------------------------------------------------------------------------

def check_python_compatibility():
    """Проверка совместимости версии Python и изоляции окружения."""
    major, minor = sys.version_info[:2]
    pr_info(f"Текущая версия Python: {sys.version.split()[0]} ({sys.executable})")

    in_venv = sys.prefix != sys.base_prefix
    if in_venv:
        pr_ok(f"Изолированное виртуальное окружение: активно ({sys.prefix})")
    else:
        pr_warn("Внимание: скрипт запущен вне изолированного окружения (рекомендуется запуск через install.bat)")

    if (major, minor) < (3, 10):
        pr_warn(f"Python {major}.{minor} может быть устаревшим. Рекомендуется Python 3.11 для работы с нейросетями.")
    elif (major, minor) > (3, 12):
        pr_warn(f"Python {major}.{minor} - новейшая версия. Для некоторых библиотек (ONNX Runtime / PyTorch) могут отсутствовать скомпилированные сборки.")
        pr_warn("Если возникнут ошибки, рекомендуется использовать Python 3.11.")
    else:
        pr_ok(f"Версия Python {major}.{minor} отлично подходит для нейросетей!")


def check_torch_cuda_compatibility(hw: dict) -> tuple[bool, str]:
    """Проверяет, поддерживает ли установленный PyTorch данную видеокарту."""
    try:
        import torch
        if not torch.cuda.is_available():
            return False, "CUDA недоступна в установленном пакете PyTorch"

        cap = torch.cuda.get_device_capability()
        target_sm = f"sm_{cap[0]}{cap[1]}"
        archs = torch.cuda.get_arch_list()

        # Для Blackwell (RTX 50-series: 5070 / 5080 / 5090 - sm_120, sm_100)
        if cap[0] >= 12 and target_sm not in archs:
            return False, f"Архитектура {target_sm} ({hw.get('name', 'GPU')}) не поддерживается установленным PyTorch (требуется CUDA 12.8+)"

        # Быстрый пробный запуск тензора на CUDA для проверки отсутствия ошибок драйвера/ядер
        t = torch.zeros(1, device='cuda')
        del t
        return True, f"{torch.__version__} (CUDA {torch.version.cuda}, {target_sm})"
    except Exception as e:
        return False, str(e)


def install_hardware_pytorch(hw: dict, reinstall: bool = False) -> bool:
    """Установка PyTorch и TorchVision с аппаратным ускорением."""
    profile = hw["profile"]

    if not reinstall and is_package_installed("torch"):
        if profile == "nvidia_cuda":
            compatible, desc = check_torch_cuda_compatibility(hw)
            if compatible:
                pr_ok(f"PyTorch уже установлен и полностью совместим с GPU: {desc}")
                return True
            else:
                pr_warn(f"Установленный PyTorch несовместим с текущей видеокартой: {desc}")
                pr_info("Удаление несовместимой сборки PyTorch...")
                run_pip(["uninstall", "-y", "torch", "torchvision"])
        else:
            pr_ok("PyTorch уже установлен.")
            return True

    pr_info("Подбор оптимальной сборки PyTorch...")

    if profile == "nvidia_cuda":
        cuda_major = hw.get("cuda_major", 12)
        gpu_name = hw.get("name", "").lower()
        is_blackwell = any(k in gpu_name for k in ["5070", "5080", "5090", "5060", "blackwell", "sm_120", "b100", "b200"])

        if is_blackwell or cuda_major >= 12.0:
            pr_info(f"Обнаружен видеоадаптер NVIDIA ({hw.get('name')}) -> Установка PyTorch с поддержкой CUDA 12.8+ (RTX 50xx Blackwell / Ada / Ampere)...")
            cmd = ["install", "--force-reinstall", "torch", "torchvision", "--index-url", "https://download.pytorch.org/whl/cu128"]
            success = run_pip(cmd, "Установка PyTorch и TorchVision (CUDA 12.8)")
            if not success and not is_blackwell:
                pr_warn("Не удалось установить PyTorch через cu128. Пробуем cu124...")
                cmd = ["install", "--force-reinstall", "torch", "torchvision", "--index-url", "https://download.pytorch.org/whl/cu124"]
                success = run_pip(cmd, "Установка PyTorch и TorchVision (CUDA 12.4)")
        else:
            pr_info("Установка PyTorch для CUDA 11.8...")
            cmd = ["install", "--force-reinstall", "torch", "torchvision", "--index-url", "https://download.pytorch.org/whl/cu118"]
            success = run_pip(cmd, "Установка PyTorch и TorchVision (CUDA 11.8)")
    else:
        pr_info("Установка легковесной CPU-версии PyTorch...")
        cmd = ["install", "torch", "torchvision", "--index-url", "https://download.pytorch.org/whl/cpu"]
        success = run_pip(cmd, "Установка PyTorch и TorchVision")

    if not success and profile == "nvidia_cuda":
        pr_warn("Пробуем универсальную установку PyTorch...")
        cmd_fallback = ["install", "torch", "torchvision"]
        success = run_pip(cmd_fallback, "Резервная установка PyTorch")

    return success


def install_inference_backend(hw: dict) -> bool:
    """Установка бэкенда инференса (ONNX Runtime GPU / DirectML / CPU / OpenVINO)."""
    profile = hw["profile"]

    if profile == "nvidia_cuda":
        pr_info("Настройка аппаратного ускорения ONNX Runtime для NVIDIA GPU...")
        # Важно: удаляем процессорный onnxruntime, чтобы не было конфликтов
        if is_package_installed("onnxruntime"):
            pr_info("Удаление процессорного пакета 'onnxruntime' для предотвращения конфликтов...")
            run_pip(["uninstall", "-y", "onnxruntime"])
        success = run_pip(["install", "onnxruntime-gpu"], "Установка onnxruntime-gpu")
        return success

    elif profile == "amd_directml":
        pr_info("Настройка ускорения DirectML для AMD Radeon...")
        if is_package_installed("onnxruntime"):
            run_pip(["uninstall", "-y", "onnxruntime"])
        success = run_pip(["install", "onnxruntime-directml"], "Установка onnxruntime-directml")
        return success

    elif profile == "intel_openvino":
        pr_info("Настройка аппаратного ускорения Intel OpenVINO...")
        run_pip(["install", "-r", str(REQUIREMENTS_OPENVINO)], "Установка OpenVINO")
        success = run_pip(["install", "onnxruntime"], "Установка onnxruntime")
        return success

    else:
        pr_info("Настройка процессорного инференса...")
        success = run_pip(["install", "onnxruntime"], "Установка onnxruntime")
        return success


def install_core_dependencies(hw: dict) -> bool:
    """Установка зависимостей из requirements.txt без конфликтов с GPU."""
    if not REQUIREMENTS_CORE.exists():
        pr_err(f"Файл {REQUIREMENTS_CORE} не найден!")
        return False

    pr_info("Установка базовых пакетов системы...")

    # Читаем requirements.txt и отфильтровываем onnxruntime (если уже установлен onnxruntime-gpu/directml)
    lines_to_install = []
    with open(REQUIREMENTS_CORE, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            # Если это onnxruntime, но мы на GPU профиле - пропускаем, чтобы не перетереть onnxruntime-gpu
            if hw["profile"] in ["nvidia_cuda", "amd_directml"] and stripped.startswith("onnxruntime"):
                continue
            # Пропускаем возможные legacy пакеты TensorRT
            if stripped.startswith("tensorrt") or stripped.startswith("nvidia-pyindex"):
                continue
            lines_to_install.append(stripped)

    # Создаём временный requirements файл
    temp_req = ROOT_DIR / ".temp_requirements.txt"
    try:
        with open(temp_req, "w", encoding="utf-8") as f:
            f.write("\n".join(lines_to_install) + "\n")

        success = run_pip(["install", "-r", str(temp_req)], "Установка базовых библиотек")
    finally:
        if temp_req.exists():
            try:
                temp_req.unlink()
            except Exception:
                pass

    return success


def install_ultralytics() -> bool:
    """Установка Ultralytics YOLO для детекции, разметки и обучения."""
    if not REQUIREMENTS_ULTRALYTICS.exists():
        pr_err(f"Файл {REQUIREMENTS_ULTRALYTICS} не найден!")
        return False

    pr_info("Установка Ultralytics YOLO (поддержка .pt моделей, трекинга и обучения)...")
    return run_pip(["install", "-r", str(REQUIREMENTS_ULTRALYTICS)], "Установка Ultralytics YOLO")


def setup_configuration_and_storage(hw: dict):
    """Инициализация config/config.json и необходимых рабочих папок."""
    pr_info("Проверка конфигурационных файлов и папок хранилища...")

    # Создание необходимых каталогов
    directories = [
        ROOT_DIR / "storage" / "datasets",
        ROOT_DIR / "storage" / "media" / "captures",
        ROOT_DIR / "storage" / "media" / "records",
        ROOT_DIR / "storage" / "logs",
        ROOT_DIR / "config" / "ultralytics" / "models",
    ]
    for d in directories:
        d.mkdir(parents=True, exist_ok=True)
    pr_ok("Папки хранилища готовы (storage/datasets, storage/media, storage/logs)")

    # Проверка config.json
    if not CONFIG_FILE.exists():
        if CONFIG_EXAMPLE.exists():
            shutil.copyfile(CONFIG_EXAMPLE, CONFIG_FILE)
            pr_ok("Создан начальный конфигурационный файл config/config.json из шаблона")
        else:
            pr_warn("Шаблон config.example.json не найден, создайте config.json вручную.")
    else:
        pr_ok("Конфигурационный файл config/config.json уже существует")


# --------------------------------------------------------------------------------
# Диагностика и проверка после установки
# --------------------------------------------------------------------------------

def verify_installation(hw: dict) -> bool:
    """Полная проверка работоспособности установленных компонентов."""
    print()
    pr("============================================================", Colors.CYAN, bold=True)
    pr("          ИТОГОВАЯ ДИАГНОСТИКА УСТАНОВКИ СИСТЕМЫ", Colors.CYAN, bold=True)
    pr("============================================================", Colors.CYAN, bold=True)

    all_ok = True

    # 1. Проверка PyTorch и CUDA
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
                    pr(f"  [!] PyTorch: {torch_ver} | Видеокарта {device_name} не поддерживается текущей сборкой!", Colors.YELLOW, bold=True)
                    pr(f"      Причина: {desc}", Colors.YELLOW)
                    pr("      Рекомендуется: pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128", Colors.YELLOW)
                    all_ok = False
                else:
                    pr(f"  [OK] PyTorch: {torch_ver} | CUDA Активна: ДА ({device_name})", Colors.GREEN)
            else:
                pr(f"  [!] PyTorch: {torch_ver} | CUDA: Нет доступа к GPU", Colors.YELLOW)
                pr("      (Возможно, требуется обновить драйвер NVIDIA или перезагрузить компьютер)", Colors.YELLOW)
                all_ok = False
        else:
            pr(f"  [OK] PyTorch: {torch_ver} (Режим: {device_name})", Colors.GREEN)
    except Exception as e:
        err_str = str(e)
        pr(f"  [ОШИБКА] PyTorch: {e}", Colors.RED)
        if "126" in err_str or "c10.dll" in err_str or "vcruntime" in err_str.lower():
            pr_warn("       -> Причина: отсутствует Microsoft Visual C++ 2015-2022 Redistributable (x64)!")
            pr_info("       -> Ссылка для установки: https://aka.ms/vs/17/release/vc_redist.x64.exe")
        all_ok = False

    # 2. Проверка ONNX Runtime
    try:
        import onnxruntime as ort
        providers = ort.get_available_providers()
        prov_str = ", ".join(providers)
        if "CUDAExecutionProvider" in providers:
            pr(f"  [OK] ONNX Runtime: {ort.__version__} | Ускоритель: CUDAExecutionProvider ({prov_str})", Colors.GREEN)
        elif "DmlExecutionProvider" in providers:
            pr(f"  [OK] ONNX Runtime: {ort.__version__} | Ускоритель: DirectML ({prov_str})", Colors.GREEN)
        elif "OpenVINOExecutionProvider" in providers:
            pr(f"  [OK] ONNX Runtime: {ort.__version__} | Ускоритель: OpenVINO ({prov_str})", Colors.GREEN)
        else:
            pr(f"  [OK] ONNX Runtime: {ort.__version__} | Провайдеры: {prov_str}", Colors.GREEN)
    except Exception as e:
        err_str = str(e)
        pr(f"  [ОШИБКА] ONNX Runtime: {e}", Colors.RED)
        if "126" in err_str or "onnxruntime_pybind11_state" in err_str:
            pr_warn("       -> Причина: отсутствует Microsoft Visual C++ 2015-2022 Redistributable (x64)!")
            pr_info("       -> Ссылка для установки: https://aka.ms/vs/17/release/vc_redist.x64.exe")
        all_ok = False

    # 3. Проверка OpenCV
    try:
        import cv2
        pr(f"  [OK] OpenCV: {cv2.__version__}", Colors.GREEN)
    except Exception as e:
        pr(f"  [ОШИБКА] OpenCV: {e}", Colors.RED)
        all_ok = False

    # 4. Проверка Ultralytics YOLO
    try:
        import ultralytics
        pr(f"  [OK] Ultralytics YOLO: {ultralytics.__version__}", Colors.GREEN)
    except Exception as e:
        pr(f"  [ОШИБКА] Ultralytics: {e}", Colors.RED)
        all_ok = False

    # 5. Проверка Flask и Flask-SocketIO
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
        pr(f"  [OK] Web Сервер: Flask {flask_ver}, SocketIO {socketio_ver}", Colors.GREEN)
    except Exception as e:
        pr(f"  [ОШИБКА] Web Сервер: {e}", Colors.RED)
        all_ok = False

    # 6. Проверка базовых моделей
    models_dir = ROOT_DIR / "config" / "ultralytics" / "models"
    available_models = list(models_dir.glob("*.pt")) + list(models_dir.glob("*.onnx"))
    if available_models:
        pr(f"  [OK] Доступно моделей детекции: {len(available_models)} ({', '.join(m.name for m in available_models[:3])}...)", Colors.GREEN)
    else:
        pr("  [ИНФО] Готовые модели в config/ultralytics/models будут загружены автоматически при первом запуске.", Colors.BLUE)

    print()
    if all_ok:
        pr("============================================================", Colors.GREEN, bold=True)
        pr("        СИСТЕМА ПОЛНОСТЬЮ ГОТОВА К РАБОТЕ! ✓", Colors.GREEN, bold=True)
        pr("============================================================", Colors.GREEN, bold=True)
        print()
        pr("  Для запуска системы выполните:", Colors.CYAN, bold=True)
        if sys.platform == "win32":
            pr("  -> Двойной клик по файлу: start.bat", Colors.YELLOW, bold=True)
        else:
            pr("  -> ./start.sh  или  venv/bin/python app.py", Colors.YELLOW, bold=True)
        print()
        pr("  Адрес веб-интерфейса в браузере: http://127.0.0.1:8080", Colors.CYAN)
        pr("  Логин/пароль по умолчанию: admin / admin (измените в настройках)", Colors.CYAN)
        print()
    else:
        pr("============================================================", Colors.YELLOW, bold=True)
        pr("  Установка завершена с замечаниями. Ознакомьтесь с сообщениями выше.", Colors.YELLOW)
        pr("============================================================", Colors.YELLOW, bold=True)

    return all_ok


# --------------------------------------------------------------------------------
# Точка входа
# --------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Автоматический установщик CVCounter")
    parser.add_argument("--profile", choices=["nvidia_cuda", "amd_directml", "intel_openvino", "cpu"], help="Принудительный выбор аппаратного профиля")
    parser.add_argument("--reinstall", action="store_true", help="Переустановить даже существующие пакеты")
    parser.add_argument("--no-color", action="store_true", help="Отключить цветовой вывод")
    args = parser.parse_args()

    if args.no_color:
        Colors.disable()

    print()
    pr("==================================================================", Colors.CYAN, bold=True)
    pr("                CVCounter - АВТОМАТИЧЕСКИЙ УСТАНОВЩИК          ", Colors.CYAN, bold=True)
    pr("     Интеллектуальная настройка окружения и видеокарты (GPU)      ", Colors.CYAN)
    pr("==================================================================", Colors.CYAN, bold=True)

    # Шаг 1: Проверка Python и системных библиотек
    pr_step(1, 6, "Проверка окружения и системных библиотек")
    check_python_compatibility()
    if sys.platform == "win32":
        ensure_vcredist()

    # Шаг 2: Анализ оборудования и видеокарты
    pr_step(2, 6, "Определение видеокарты и оборудования")
    hw = detect_hardware_profile(args.profile)
    pr(f"  Выбранный профиль: {hw['profile'].upper()}", Colors.BOLD)
    pr(f"  Оборудование: {hw['name']}")
    if hw.get("driver_version"):
        pr(f"  Версия видеодрайвера: {hw['driver_version']}")
    if hw.get("cuda_version"):
        pr(f"  Поддерживаемая версия CUDA: {hw['cuda_version']}")
    if hw.get("all_gpus"):
        pr(f"  Все видеоадаптеры в системе: {', '.join(hw['all_gpus'])}")

    # Шаг 3: Обновление менеджера пакетов pip
    pr_step(3, 6, "Обновление pip, setuptools и wheel")
    sanitize_pip_config()
    run_pip(["install", "--upgrade", "pip", "setuptools", "wheel"], "Обновление базовых инструментов сборки")

    # Шаг 4: Установка PyTorch с аппаратным ускорением
    pr_step(4, 6, "Установка PyTorch с аппаратным ускорением")
    install_hardware_pytorch(hw, reinstall=args.reinstall)

    # Шаг 5: Установка бэкенда инференса и всех зависимостей
    pr_step(5, 6, "Установка ONNX Runtime, Ultralytics и библиотек проекта")
    install_inference_backend(hw)
    install_core_dependencies(hw)
    install_ultralytics()

    # Шаг 6: Настройка конфигурации и папок
    pr_step(6, 6, "Настройка конфигурации и каталогов хранилища")
    setup_configuration_and_storage(hw)

    # Финальная диагностика
    success = verify_installation(hw)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
