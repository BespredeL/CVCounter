# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from __future__ import annotations

import glob
from pathlib import Path
from typing import Callable, Iterable, Optional

import yaml

from system.utils.paths import ensure_dir, get_project_root, set_project_root


class TrainingCancelledError(RuntimeError):
    """Raised when training is cancelled by the user."""
    pass


DEFAULT_BASE_MODEL = 'yolo11n.pt'
DEFAULT_TASK = 'detect'
DEFAULT_IMG_SIZE = 640
DEFAULT_EPOCHS = 100
IMAGE_EXTENSIONS = ('jpg', 'jpeg', 'png', 'bmp', 'webp')

_PROJECT_ROOT: Optional[Path] = None
CFG_DIR: Path
MODELS_DIR: Path
RUNS_DIR: Path
DATASETS_DIR: Path


def resolve_training_paths(project_root: Optional[Path | str] = None) -> tuple[Path, Path, Path, Path]:
    """
    Resolve cfg/models/runs/datasets directories with ultralytics-first layout.

    Args:
        project_root: Optional project root override.

    Returns:
        Tuple of (cfg_dir, models_dir, runs_dir, datasets_dir).
    """
    root = Path(project_root) if project_root else Path(get_project_root())
    ultra = root / 'config' / 'ultralytics'
    legacy = root / 'config'

    cfg_dir = ultra / 'cfg' if (ultra / 'cfg').is_dir() or not (legacy / 'cfg').is_dir() else legacy / 'cfg'
    models_dir = (
        ultra / 'models' if (ultra / 'models').is_dir() or not (legacy / 'models').is_dir()
        else legacy / 'models'
    )
    runs_dir = ultra / 'runs' if (ultra / 'runs').is_dir() or not (legacy / 'runs').is_dir() else legacy / 'runs'
    datasets_dir = root / 'storage' / 'datasets'
    return cfg_dir, models_dir, runs_dir, datasets_dir


def _refresh_globals(project_root: Optional[Path | str] = None) -> None:
    """
    Refresh the global variables.
    
    Args:
        project_root (Optional[Path | str]): The project root
    
    Returns:
        None
    """
    global _PROJECT_ROOT, CFG_DIR, MODELS_DIR, RUNS_DIR, DATASETS_DIR
    root = Path(project_root) if project_root else Path(get_project_root())
    _PROJECT_ROOT = root
    CFG_DIR, MODELS_DIR, RUNS_DIR, DATASETS_DIR = resolve_training_paths(root)


_refresh_globals()


def setup_directories(project_root: Optional[Path | str] = None) -> None:
    """
    Ensure training directories exist and refresh module path globals.
    
    Args:
        project_root (Optional[Path | str]): The project root
    
    Returns:
        None
    """
    root = Path(project_root) if project_root else Path(__file__).resolve().parents[2]
    set_project_root(str(root))
    _refresh_globals(root)
    for path in (CFG_DIR, MODELS_DIR, RUNS_DIR, DATASETS_DIR):
        ensure_dir(str(path))


def resolve_device(device: Optional[str]) -> str | int:
    """
    Resolve the device.
    
    Args:
        device (Optional[str]): The device
    
    Returns:
        str | int: The resolved device
    """
    try:
        import torch
        cuda_ok = torch.cuda.is_available()
    except ImportError:
        cuda_ok = False

    if device is None:
        return 0 if cuda_ok else 'cpu'
    if str(device).lower() == 'auto':
        return 0 if cuda_ok else 'cpu'
    if str(device).isdigit():
        return int(device)
    return device


def config_yaml_path(config_name: str) -> Path:
    """
    Get the path to the config YAML file.
    
    Args:
        config_name (str): The name of the config
    
    Returns:
        Path: The path to the config YAML file
    """
    name = config_name.removesuffix('.yaml')
    return CFG_DIR / f'{name}.yaml'


def list_configs() -> list[str]:
    """
    List the configs.
    
    Returns:
        list[str]: The list of configs
    """
    _refresh_globals()
    if not CFG_DIR.is_dir():
        return []
    return sorted(path.stem for path in CFG_DIR.glob('*.yaml'))


OFFICIAL_BASE_MODELS: dict[str, dict] = {
    'yolo11n.pt': {
        'name': 'YOLO11 Nano',
        'task': 'detect',
        'size_mb': 5.6,
        'speed': 'Ultra Fast',
        'recommended': True,
        'description': 'Наиболее быстрая и лёгкая модель. Идеально для реального времени и CPU/встраиваемых систем.',
        'url': 'https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt',
    },
    'yolo11s.pt': {
        'name': 'YOLO11 Small',
        'task': 'detect',
        'size_mb': 19.3,
        'speed': 'Fast',
        'recommended': False,
        'description': 'Оптимальный баланс между скоростью и точностью.',
        'url': 'https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11s.pt',
    },
    'yolo11m.pt': {
        'name': 'YOLO11 Medium',
        'task': 'detect',
        'size_mb': 40.7,
        'speed': 'Balanced',
        'recommended': False,
        'description': 'Высокая точность для сложных объектов и детализированных сцен.',
        'url': 'https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11m.pt',
    },
    'yolov8n.pt': {
        'name': 'YOLOv8 Nano',
        'task': 'detect',
        'size_mb': 6.5,
        'speed': 'Ultra Fast',
        'recommended': False,
        'description': 'Проверенная лёгкая архитектура предыдущего поколения.',
        'url': 'https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8n.pt',
    },
    'yolov8s.pt': {
        'name': 'YOLOv8 Small',
        'task': 'detect',
        'size_mb': 22.5,
        'speed': 'Fast',
        'recommended': False,
        'description': 'Средняя модель YOLOv8 для видеокарт с умеренной производительностью.',
        'url': 'https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8s.pt',
    },
    'yolov8m.pt': {
        'name': 'YOLOv8 Medium',
        'task': 'detect',
        'size_mb': 52.0,
        'speed': 'Medium',
        'recommended': False,
        'description': 'Точная модель YOLOv8 для серверов с производительными GPU.',
        'url': 'https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8m.pt',
    },
}


def get_base_model_download_candidates(clean_name: str) -> list[str]:
    """Return an ordered list of candidate download URLs for a base model."""
    urls = []
    model_info = OFFICIAL_BASE_MODELS.get(clean_name, {})
    custom_url = model_info.get('url')
    if custom_url:
        urls.append(custom_url)

    tag = 'v8.3.0'
    series = None
    if clean_name.startswith('yolo11'):
        series = 'YOLO11'
        tag = 'v8.3.0'
    elif clean_name.startswith('yolov8'):
        series = 'YOLOv8'
        tag = 'v8.2.0'
    elif clean_name.startswith('yolov5'):
        series = 'YOLOv5'
        tag = 'v7.0'
    elif clean_name.startswith('yolov9'):
        series = 'YOLOv9'
        tag = 'v8.2.0'
    elif clean_name.startswith('yolov10'):
        series = 'YOLOv10'
        tag = 'v8.2.0'

    gh_url = f'https://github.com/ultralytics/assets/releases/download/{tag}/{clean_name}'
    if gh_url not in urls:
        urls.append(gh_url)

    if series:
        hf_mirror = f'https://hf-mirror.com/Ultralytics/{series}/resolve/main/{clean_name}'
        if hf_mirror not in urls:
            urls.append(hf_mirror)
        hf_direct = f'https://huggingface.co/Ultralytics/{series}/resolve/main/{clean_name}'
        if hf_direct not in urls:
            urls.append(hf_direct)

    return urls


def _download_file_requests(
        url: str,
        tmp_path: Path,
        clean_name: str,
        progress_callback: Optional[Callable[[dict], None]] = None,
) -> bool:
    import requests
    import urllib3
    urllib3.disable_warnings()

    # Try with verify=True first, fall back to verify=False if certificate issue
    for verify_ssl in (True, False):
        try:
            with requests.get(
                url,
                stream=True,
                timeout=(10, 60),
                verify=verify_ssl,
                headers={'User-Agent': 'Mozilla/5.0 (CVCounterWEB Auto-Downloader)'}
            ) as response:
                if response.status_code != 200:
                    return False
                total_size = int(response.headers.get('Content-Length') or 0)
                downloaded = 0
                chunk_size = 128 * 1024
                last_reported = 0

                with open(tmp_path, 'wb') as out_f:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if not chunk:
                            continue
                        out_f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            pct = int((downloaded / total_size) * 100)
                            if pct >= last_reported + 5 or downloaded == total_size:
                                last_reported = pct
                                if progress_callback:
                                    progress_callback({
                                        'status': 'downloading',
                                        'model': clean_name,
                                        'model_name': clean_name,
                                        'percent': pct,
                                        'progress': pct,
                                        'downloaded': downloaded,
                                        'total': total_size,
                                        'message': f'Downloading {clean_name}: {pct}%',
                                    })
                if total_size > 0 and downloaded < int(total_size * 0.95):
                    raise IOError(f"Incomplete download: {downloaded}/{total_size} bytes")
                return True
        except requests.exceptions.SSLError:
            if verify_ssl:
                continue
            raise
        except Exception:
            raise
    return False


def _download_file_urllib(
        url: str,
        tmp_path: Path,
        clean_name: str,
        progress_callback: Optional[Callable[[dict], None]] = None,
) -> bool:
    import urllib.request
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0 (CVCounterWEB Auto-Downloader)'}
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        total_size = int(response.headers.get('Content-Length') or 0)
        downloaded = 0
        chunk_size = 128 * 1024
        last_reported = 0

        with open(tmp_path, 'wb') as out_f:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                out_f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    pct = int((downloaded / total_size) * 100)
                    if pct >= last_reported + 5 or downloaded == total_size:
                        last_reported = pct
                        if progress_callback:
                            progress_callback({
                                'status': 'downloading',
                                'model': clean_name,
                                'model_name': clean_name,
                                'percent': pct,
                                'progress': pct,
                                'downloaded': downloaded,
                                'total': total_size,
                                'message': f'Downloading {clean_name}: {pct}%',
                            })
    return True


def download_base_model(
        model_name: str,
        progress_callback: Optional[Callable[[dict], None]] = None,
        project_root: Optional[Path | str] = None,
) -> Path:
    """
    Download an official YOLO base model to MODELS_DIR with multi-mirror fallback.

    Args:
        model_name: Name of the model (e.g. 'yolo11n.pt').
        progress_callback: Optional callback receiving progress dicts.
        project_root: Optional project root override.

    Returns:
        Path to the downloaded model weights file.
    """
    import shutil
    from system.utils.logger import Logger

    logger = Logger()
    setup_directories(project_root)
    clean_name = Path(model_name).name
    dest_path = MODELS_DIR / clean_name

    # 1. Check local candidate paths (MODELS_DIR, root, config/models)
    root = _PROJECT_ROOT or Path(get_project_root())
    candidate_paths = [
        dest_path,
        root / clean_name,
        root / 'config' / 'models' / clean_name,
        root / 'config' / 'ultralytics' / 'models' / clean_name,
    ]
    for cand in candidate_paths:
        if cand.is_file() and cand.stat().st_size > 1024 * 1024:
            if cand.resolve() != dest_path.resolve():
                try:
                    ensure_dir(str(dest_path.parent))
                    shutil.copy2(str(cand), str(dest_path))
                except Exception as cp_err:
                    logger.warning(f"Could not copy {cand} to {dest_path}: {cp_err}")
            if dest_path.is_file() and dest_path.stat().st_size > 1024 * 1024:
                if progress_callback:
                    progress_callback({
                        'status': 'done',
                        'model': clean_name,
                        'model_name': clean_name,
                        'percent': 100,
                        'progress': 100,
                        'message': f'Model {clean_name} is already available',
                    })
                return dest_path

    candidate_urls = get_base_model_download_candidates(clean_name)
    logger.info(f"Downloading base model '{clean_name}' from candidates: {candidate_urls}")

    if progress_callback:
        progress_callback({
            'status': 'starting',
            'model': clean_name,
            'model_name': clean_name,
            'percent': 0,
            'progress': 0,
            'message': f'Starting download of {clean_name}...',
        })

    tmp_path = dest_path.with_suffix('.pt.tmp')
    last_error: Optional[Exception] = None

    # Try downloading via requests across candidate mirrors
    for url in candidate_urls:
        try:
            logger.info(f"Attempting download of {clean_name} from: {url}")
            success = _download_file_requests(url, tmp_path, clean_name, progress_callback)
            if not success:
                success = _download_file_urllib(url, tmp_path, clean_name, progress_callback)
            if success and tmp_path.is_file() and tmp_path.stat().st_size > 1024 * 1024:
                if dest_path.is_file():
                    dest_path.unlink()
                tmp_path.rename(dest_path)
                logger.info(f"Successfully downloaded base model: {dest_path}")
                if progress_callback:
                    progress_callback({
                        'status': 'done',
                        'model': clean_name,
                        'model_name': clean_name,
                        'percent': 100,
                        'progress': 100,
                        'message': f'Successfully downloaded {clean_name}',
                    })
                return dest_path
        except Exception as exc:
            logger.warning(f"Download candidate {url} failed: {exc}")
            last_error = exc
            if tmp_path.is_file():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass

    # Fallback to Ultralytics built-in downloader
    logger.info(f"Trying Ultralytics fallback for {clean_name}...")
    try:
        from ultralytics import YOLO
        _ = YOLO(clean_name)
        cwd_cand = Path(clean_name)
        if cwd_cand.is_file() and cwd_cand.stat().st_size > 1024 * 1024:
            if dest_path.is_file():
                dest_path.unlink()
            cwd_cand.rename(dest_path)
            if progress_callback:
                progress_callback({
                    'status': 'done',
                    'model': clean_name,
                    'model_name': clean_name,
                    'percent': 100,
                    'progress': 100,
                    'message': f'Successfully downloaded {clean_name}',
                })
            return dest_path
    except Exception as fb_exc:
        logger.error(f"Ultralytics fallback failed for {clean_name}: {fb_exc}")
        if not last_error:
            last_error = fb_exc

    err_text = str(last_error or "Unknown error")
    if 'getaddrinfo' in err_text or '11001' in err_text:
        err_msg = (
            f"Не удалось подключиться к серверам загрузки для '{clean_name}' (ошибка DNS: {err_text}). "
            f"Проверьте доступ в интернет/DNS или поместите файл вручную в папку: config/ultralytics/models/{clean_name}"
        )
    else:
        err_msg = (
            f"Не удалось загрузить модель '{clean_name}': {err_text}. "
            f"Вы можете вручную поместить файл модели в: config/ultralytics/models/{clean_name}"
        )
    raise RuntimeError(err_msg)


def get_available_base_models() -> list[dict]:
    """
    Get base models with installation status, size, and metadata.

    Returns:
        List of model dictionaries.
    """
    _refresh_globals()
    installed_files = {}
    if MODELS_DIR.is_dir():
        for path in sorted(MODELS_DIR.glob('*.pt')):
            installed_files[path.name] = path

    models = []
    # Add official curated models first
    for name, info in OFFICIAL_BASE_MODELS.items():
        is_installed = name in installed_files
        file_size_mb = (
            round(installed_files[name].stat().st_size / (1024 * 1024), 1)
            if is_installed else info.get('size_mb', 0.0)
        )
        models.append({
            'name': name,
            'display_name': info.get('name', name),
            'task': info.get('task', 'detect'),
            'task_type': info.get('task', 'detect'),
            'size_mb': file_size_mb,
            'speed': info.get('speed', 'Fast'),
            'recommended': info.get('recommended', False),
            'description': info.get('description', ''),
            'installed': is_installed,
            'path': str(installed_files[name]) if is_installed else None,
        })

    # Add any extra custom .pt models in MODELS_DIR
    for name, path in installed_files.items():
        if name not in OFFICIAL_BASE_MODELS:
            size_mb = round(path.stat().st_size / (1024 * 1024), 1)
            models.append({
                'name': name,
                'display_name': f'Custom: {name}',
                'task': 'detect',
                'task_type': 'detect',
                'size_mb': size_mb,
                'speed': 'Custom',
                'recommended': False,
                'description': 'Пользовательская модель в папке моделей.',
                'installed': True,
                'path': str(path),
            })

    return models


def list_base_models() -> list[str]:
    """
    List the base models.
    
    Returns:
        list[str]: The list of base models
    """
    _refresh_globals()
    if not MODELS_DIR.is_dir():
        return []
    names = []
    for path in sorted(MODELS_DIR.glob('*.pt')):
        names.append(path.name)
    return names


def read_dataset_root(data_yaml: Path) -> Optional[Path]:
    """
    Read the dataset root.
    
    Args:
        data_yaml (Path): The path to the data YAML file
    
    Returns:
        Optional[Path]: The dataset root
    """
    if not data_yaml.is_file():
        return None
    with open(data_yaml, encoding='utf-8') as file:
        data = yaml.safe_load(file) or {}
    raw_path = data.get('path')
    if not raw_path:
        return None
    dataset_root = Path(raw_path)
    if not dataset_root.is_absolute():
        dataset_root = (data_yaml.parent / dataset_root).resolve()
    return dataset_root


def best_weights_path(config_name: str, task: str = DEFAULT_TASK) -> Path:
    """
    Get the path to the best weights file.
    
    Args:
        config_name (str): The name of the config
        task (str): The task to get the best weights path for
    
    Returns:
        Path: The path to the best weights file
    """
    _refresh_globals()
    name = config_name.removesuffix('.yaml')
    return RUNS_DIR / task / name / 'weights' / 'best.pt'


def load_model(model_path: Path):
    """
    Load a model.
    
    Args:
        model_path (Path): The path to the model
    
    Returns:
        The loaded model instance
    """
    if not model_path.is_file():
        raise FileNotFoundError(f'Model not found: {model_path}')
    from ultralytics import YOLO
    return YOLO(str(model_path))


def _collect_files(directory: Path, extensions: Iterable[str]) -> list[Path]:
    """
    Collect files from a directory.
    
    Args:
        directory (Path): The directory to collect files from
        extensions (Iterable[str]): The extensions to collect
    
    Returns:
        list[Path]: The collected files
    """
    if not directory.is_dir():
        return []
    files: list[Path] = []
    for extension in extensions:
        files.extend(Path(path) for path in glob.glob(str(directory / f'*.{extension}')))
        files.extend(Path(path) for path in glob.glob(str(directory / f'*.{extension.upper()}')))
    return files


def dedupe_val_from_train(dataset_root: Path) -> int:
    """
    Remove validation images/labels duplicated in train folders. Returns removed count.
    
    Args:
        dataset_root (Path): The root of the dataset
    
    Returns:
        int: The number of removed files
    """
    images_val = dataset_root / 'images' / 'val'
    labels_val = dataset_root / 'labels' / 'val'
    images_train = dataset_root / 'images' / 'train'
    labels_train = dataset_root / 'labels' / 'train'

    val_images = _collect_files(images_val, IMAGE_EXTENSIONS)
    val_labels = _collect_files(labels_val, ('txt',))

    removed = 0
    for file_path in val_images:
        duplicate = images_train / file_path.name
        if duplicate.is_file():
            duplicate.unlink()
            removed += 1

    for file_path in val_labels:
        duplicate = labels_train / file_path.name
        if duplicate.is_file():
            duplicate.unlink()
            removed += 1

    return removed


def train_model(
        config_name: str,
        base_model: str,
        epochs: int,
        img_size: int,
        batch: int,
        device: str | int,
        task: str,
        export_format: Optional[str] = None,
        dedupe_val: bool = False,
        progress_callback: Optional[Callable[[dict], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
        project_root: Optional[Path | str] = None,
) -> Path:
    """
    Train a YOLO model from a dataset YAML config.

    Args:
        config_name: YAML stem in cfg dir.
        base_model: Base weights filename or absolute path.
        epochs: Number of epochs.
        img_size: Training image size.
        batch: Batch size (-1 = auto).
        device: Torch device.
        task: Ultralytics task name.
        export_format: Optional post-train export format.
        dedupe_val: Remove train duplicates of val files.
        progress_callback: Optional callback receiving progress dicts.
        cancel_check: Optional callback returning True when cancel was requested.
        project_root: Optional project root override.

    Returns:
        Path to best.pt weights.
    """
    setup_directories(project_root)
    data_yaml = config_yaml_path(config_name)
    if not data_yaml.is_file():
        raise FileNotFoundError(f'Dataset config not found: {data_yaml}')

    if dedupe_val:
        dataset_root = read_dataset_root(data_yaml)
        if dataset_root is None:
            raise ValueError(f"Cannot dedupe: 'path' is missing in {data_yaml}")
        if not dataset_root.is_dir():
            raise FileNotFoundError(f'Dataset directory not found: {dataset_root}')
        dedupe_val_from_train(dataset_root)

    base_model_path = Path(base_model)
    if not base_model_path.is_file():
        base_model_path = MODELS_DIR / base_model

    if not base_model_path.is_file():
        model_name = Path(base_model).name
        if model_name in OFFICIAL_BASE_MODELS:
            if progress_callback is not None:
                progress_callback({
                    'event': 'log',
                    'message': f"Base model '{model_name}' not found locally. Auto-downloading...",
                })
            base_model_path = download_base_model(
                model_name,
                progress_callback=progress_callback,
                project_root=project_root,
            )
        else:
            raise FileNotFoundError(f'Model not found: {base_model_path}')

    model = load_model(base_model_path)
    run_name = config_name.removesuffix('.yaml')

    callbacks_attached = False
    if progress_callback is not None:
        def _on_fit_epoch_end(trainer) -> None:
            metrics = getattr(trainer, 'metrics', None) or {}
            payload = {
                'event': 'epoch_end',
                'epoch': int(getattr(trainer, 'epoch', 0)) + 1,
                'epochs': int(getattr(trainer, 'epochs', epochs)),
                'metrics': {k: float(v) for k, v in dict(metrics).items() if isinstance(v, (int, float))},
            }
            progress_callback(payload)

        model.add_callback('on_fit_epoch_end', _on_fit_epoch_end)
        callbacks_attached = True

    if cancel_check is not None:
        def _on_batch_cancel(trainer) -> None:
            if cancel_check():
                trainer.stop = True

        def _on_epoch_cancel(trainer) -> None:
            if cancel_check():
                trainer.stop = True

        model.add_callback('on_train_batch_end', _on_batch_cancel)
        model.add_callback('on_fit_epoch_end', _on_epoch_cancel)
        callbacks_attached = True

    if progress_callback is not None:
        progress_callback({
            'event': 'start',
            'config': run_name,
            'epochs': epochs,
            'imgsz': img_size,
            'batch': batch,
            'device': str(device),
        })

    model.train(
        data=str(data_yaml),
        imgsz=img_size,
        epochs=epochs,
        batch=batch,
        name=run_name,
        device=device,
        project=str(RUNS_DIR / task),
        exist_ok=True,
    )

    if cancel_check is not None and cancel_check():
        raise TrainingCancelledError('Training was cancelled by user')

    weights = best_weights_path(run_name, task)
    if not weights.is_file():
        raise FileNotFoundError(f'Training finished but weights not found: {weights}')

    if progress_callback is not None:
        progress_callback({'event': 'complete', 'weights': str(weights)})

    if export_format:
        export_path = export_weights(weights, export_format, device)
        if progress_callback is not None:
            progress_callback({'event': 'exported', 'path': str(export_path), 'format': export_format})

    if callbacks_attached:
        # Keeps callbacks on the model instance; nothing else to clean.
        pass

    return weights


def export_weights(weights_path: Path, export_format: str, device: str | int) -> Path:
    """
    Export weights.
    
    Args:
        weights_path (Path): The path to the weights
        export_format (str): The format to export
        device (str | int): The device to export
    
    Returns:
        Path: The path to the exported weights
    """
    model = load_model(Path(weights_path))
    result = model.export(format=export_format, device=device, simplify=True)
    export_path = Path(result) if result else Path(weights_path).with_suffix(f'.{export_format}')
    return export_path
