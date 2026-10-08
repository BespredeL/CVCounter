# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 28.07.2026
# Updated: 30.07.2026
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
