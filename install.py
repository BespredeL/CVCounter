# -*- coding: utf-8 -*-
"""
CVCounterWEB — Универсальный автоматический установщик системы.
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

# Принудительная установка кодировки UTF-8 для вывода в консоль
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

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
    pr(f"  ✓ {text}", Colors.GREEN)

def pr_info(text: str):
    pr(f"  ℹ {text}", Colors.BLUE)

def pr_warn(text: str):
    pr(f"  ⚠ {text}", Colors.YELLOW, bold=True)

def pr_err(text: str):
    pr(f"  ✖ {text}", Colors.RED, bold=True)


ROOT_DIR = Path(__file__).resolve().parent
REQUIREMENTS_CORE = ROOT_DIR / "requirements.txt"
REQUIREMENTS_ULTRALYTICS = ROOT_DIR / "requirements-ultralytics.txt"
REQUIREMENTS_OPENVINO = ROOT_DIR / "requirements-openvino.txt"
CONFIG_EXAMPLE = ROOT_DIR / "config" / "config.example.json"
CONFIG_FILE = ROOT_DIR / "config" / "config.json"


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

    # Поиск nvidia-smi
    nvidia_smi_cmd = shutil.which("nvidia-smi")
    if not nvidia_smi_cmd and sys.platform == "win32":
        for possible_path in [
            r"C:\Windows\System32\nvidia-smi.exe",
            r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe"
        ]:
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
        cuda_major = 12
        if cuda:
            try:
                cuda_major = float(cuda.split()[0])
            except Exception:
                cuda_major = 12

        return {
            "profile": "nvidia_cuda",
            "name": nv["name"] or "NVIDIA GPU",
            "driver_version": driver,
            "cuda_version": cuda,
            "cuda_major": cuda_major,
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
    """Проверка совместимости версии Python."""
    major, minor = sys.version_info[:2]
    pr_info(f"Текущая версия Python: {sys.version.split()[0]} ({sys.executable})")

    if (major, minor) < (3, 10):
        pr_warn(f"Python {major}.{minor} может быть устаревшим. Рекомендуется Python 3.11 для работы с нейросетями.")
    elif (major, minor) > (3, 12):
        pr_warn(f"Python {major}.{minor} — новейшая версия. Для некоторых библиотек (ONNX Runtime / PyTorch) могут отсутствовать скомпилированные сборки.")
        pr_warn("Если возникнут ошибки, рекомендуется использовать Python 3.11.")
    else:
        pr_ok(f"Версия Python {major}.{minor} отлично подходит для нейросетей!")


def install_hardware_pytorch(hw: dict, reinstall: bool = False) -> bool:
    """Установка PyTorch и TorchVision с аппаратным ускорением."""
    profile = hw["profile"]

    if not reinstall and is_package_installed("torch"):
        # Проверим, работает ли уже CUDA, если профиль NVIDIA
        if profile == "nvidia_cuda":
            try:
                import torch
                if torch.cuda.is_available():
                    pr_ok(f"PyTorch уже установлен с поддержкой CUDA: {torch.__version__} (CUDA {torch.version.cuda})")
                    return True
                else:
                    pr_info("PyTorch установлен, но без поддержки CUDA. Выполняется установка версии с CUDA...")
            except Exception:
                pass
        else:
            pr_ok("PyTorch уже установлен.")
            return True

    pr_info("Подбор оптимальной сборки PyTorch...")

    if profile == "nvidia_cuda":
        cuda_major = hw.get("cuda_major", 12)
        if cuda_major >= 12.0:
            pr_info(f"Обнаружен драйвер с поддержкой CUDA {hw.get('cuda_version')} -> Установка PyTorch (CUDA 12.4+)...")
            cmd = ["install", "torch", "torchvision", "--index-url", "https://download.pytorch.org/whl/cu124"]
        else:
            pr_info("Установка PyTorch для CUDA 11.8...")
            cmd = ["install", "torch", "torchvision", "--index-url", "https://download.pytorch.org/whl/cu118"]
    else:
        pr_info("Установка легковесной CPU-версии PyTorch...")
        cmd = ["install", "torch", "torchvision", "--index-url", "https://download.pytorch.org/whl/cpu"]

    success = run_pip(cmd, "Установка PyTorch и TorchVision")
    if not success and profile == "nvidia_cuda":
        pr_warn("Не удалось установить PyTorch с CUDA через cu124. Пробуем универсальную установку...")
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
            # Если это onnxruntime, но мы на GPU профиле — пропускаем, чтобы не перетереть onnxruntime-gpu
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
                pr(f"  [OK] PyTorch: {torch_ver} | CUDA Активна: ДА ({device_name})", Colors.GREEN)
            else:
                pr(f"  [ВНИМАНИЕ] PyTorch: {torch_ver} | CUDA: Нет доступа к GPU", Colors.YELLOW)
                pr("       (Возможно, требуется обновить драйвер NVIDIA или перезагрузить компьютер)", Colors.YELLOW)
                all_ok = False
        else:
            pr(f"  [OK] PyTorch: {torch_ver} (Режим: {device_name})", Colors.GREEN)
    except Exception as e:
        pr(f"  [ОШИБКА] PyTorch: {e}", Colors.RED)
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
        pr(f"  [ОШИБКА] ONNX Runtime: {e}", Colors.RED)
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
        pr("  Адрес веб-интерфейса в браузере: http://127.0.0.1:5000  (или http://localhost:8080)", Colors.CYAN)
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
    parser = argparse.ArgumentParser(description="Автоматический установщик CVCounterWEB")
    parser.add_argument("--profile", choices=["nvidia_cuda", "amd_directml", "intel_openvino", "cpu"], help="Принудительный выбор аппаратного профиля")
    parser.add_argument("--reinstall", action="store_true", help="Переустановить даже существующие пакеты")
    parser.add_argument("--no-color", action="store_true", help="Отключить цветовой вывод")
    args = parser.parse_args()

    if args.no_color:
        Colors.disable()

    print()
    pr("==================================================================", Colors.CYAN, bold=True)
    pr("                CVCounterWEB — АВТОМАТИЧЕСКИЙ УСТАНОВЩИК          ", Colors.CYAN, bold=True)
    pr("     Интеллектуальная настройка окружения и видеокарты (GPU)      ", Colors.CYAN)
    pr("==================================================================", Colors.CYAN, bold=True)

    # Шаг 1: Проверка Python
    pr_step(1, 6, "Проверка версии интерпретатора Python")
    check_python_compatibility()

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
