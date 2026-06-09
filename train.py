# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 01.11.2023
# Updated: 09.06.2026
# Website: https://bespredel.name

"""
Train and export Ultralytics YOLO models for CVCounter.

Examples:
    python train.py list
    python train.py train --config yolov8_disk_in
    python train.py train --config yolov8_disk_in --epochs 200 --export onnx
    python train.py export --config yolov8_disk_in --export engine
"""

from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path
from typing import Iterable, Optional

import torch
import yaml
from ultralytics import YOLO

from system.utils.paths import ensure_dir, set_project_root

PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_DIR = PROJECT_ROOT / 'config'
CFG_DIR = CONFIG_DIR / 'cfg'
MODELS_DIR = CONFIG_DIR / 'models'
RUNS_DIR = CONFIG_DIR / 'runs'
DATASETS_DIR = PROJECT_ROOT / 'storage' / 'datasets'

DEFAULT_BASE_MODEL = 'yolo11n.pt'
DEFAULT_TASK = 'detect'
DEFAULT_IMG_SIZE = 640
DEFAULT_EPOCHS = 100
IMAGE_EXTENSIONS = ('jpg', 'jpeg', 'png', 'bmp', 'webp')


def setup_directories() -> None:
    set_project_root(str(PROJECT_ROOT))
    for path in (CFG_DIR, MODELS_DIR, RUNS_DIR, DATASETS_DIR):
        ensure_dir(str(path))


def resolve_device(device: Optional[str]) -> str | int:
    if device is None:
        return 0 if torch.cuda.is_available() else 'cpu'
    if device.lower() == 'auto':
        return 0 if torch.cuda.is_available() else 'cpu'
    if device.isdigit():
        return int(device)
    return device


def config_yaml_path(config_name: str) -> Path:
    name = config_name.removesuffix('.yaml')
    return CFG_DIR / f'{name}.yaml'


def list_configs() -> list[str]:
    if not CFG_DIR.is_dir():
        return []
    return sorted(path.stem for path in CFG_DIR.glob('*.yaml'))


def print_configs() -> None:
    configs = list_configs()
    if not configs:
        print(f'No YAML configs found in {CFG_DIR}')
        return
    print('Available training configs:')
    for name in configs:
        data_path = config_yaml_path(name)
        dataset_root = read_dataset_root(data_path)
        suffix = f' -> {dataset_root}' if dataset_root else ''
        print(f'  - {name}{suffix}')


def read_dataset_root(data_yaml: Path) -> Optional[Path]:
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
    name = config_name.removesuffix('.yaml')
    return RUNS_DIR / task / name / 'weights' / 'best.pt'


def load_model(model_path: Path) -> YOLO:
    if not model_path.is_file():
        raise FileNotFoundError(f'Model not found: {model_path}')
    return YOLO(str(model_path))


def _collect_files(directory: Path, extensions: Iterable[str]) -> list[Path]:
    if not directory.is_dir():
        return []
    files: list[Path] = []
    for extension in extensions:
        files.extend(Path(path) for path in glob.glob(str(directory / f'*.{extension}')))
    return files


def dedupe_val_from_train(dataset_root: Path) -> None:
    """
    Remove validation images/labels from train folders when they were duplicated.
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
            print(f'Removed duplicate train image: {duplicate}')

    for file_path in val_labels:
        duplicate = labels_train / file_path.name
        if duplicate.is_file():
            duplicate.unlink()
            removed += 1
            print(f'Removed duplicate train label: {duplicate}')

    if removed == 0:
        print('No duplicated train/val files removed.')
    else:
        print(f'Removed {removed} duplicated file(s) from train set.')


def train_model(
        config_name: str,
        base_model: str,
        epochs: int,
        img_size: int,
        batch: int,
        device: str | int,
        task: str,
        export_format: Optional[str],
        dedupe_val: bool,
) -> Path:
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

    base_model_path = MODELS_DIR / base_model
    model = load_model(base_model_path)
    run_name = config_name.removesuffix('.yaml')

    print(f'Training {run_name}')
    print(f'  data: {data_yaml}')
    print(f'  base model: {base_model_path}')
    print(f'  device: {device}')
    print(f'  epochs: {epochs}, imgsz: {img_size}, batch: {batch}')

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

    weights = best_weights_path(run_name, task)
    if not weights.is_file():
        raise FileNotFoundError(f'Training finished but weights not found: {weights}')

    print(f'Training complete: {weights}')

    if export_format:
        export_weights(weights, export_format, device)

    return weights


def export_weights(weights_path: Path, export_format: str, device: str | int) -> Path:
    model = load_model(weights_path)
    print(f'Exporting {weights_path} -> {export_format}')
    result = model.export(format=export_format, device=device, simplify=True)
    export_path = Path(result) if result else weights_path.with_suffix(f'.{export_format}')
    print(f'Export complete: {export_path}')
    return export_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Train and export YOLO models for CVCounter.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            'Project layout:\n'
            '  config/cfg/<name>.yaml   dataset definition\n'
            '  config/models/           base weights (.pt)\n'
            '  config/runs/detect/      training output\n'
            '  storage/datasets/        images and labels\n'
        ),
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    list_parser = subparsers.add_parser('list', help='List available dataset YAML configs')
    list_parser.set_defaults(func=lambda args: print_configs())

    train_parser = subparsers.add_parser('train', help='Train a model from a base checkpoint')
    train_parser.add_argument('--config', '-c', required=True, help='YAML name in config/cfg (without .yaml)')
    train_parser.add_argument('--base-model', '-m', default=DEFAULT_BASE_MODEL, help='Base weights in config/models/')
    train_parser.add_argument('--epochs', '-e', type=int, default=DEFAULT_EPOCHS)
    train_parser.add_argument('--imgsz', type=int, default=DEFAULT_IMG_SIZE)
    train_parser.add_argument('--batch', type=int, default=-1, help='Batch size (-1 = auto)')
    train_parser.add_argument('--device', default='auto', help='cuda device id, cpu, or auto')
    train_parser.add_argument('--task', default=DEFAULT_TASK, choices=('detect', 'segment', 'classify', 'pose'))
    train_parser.add_argument('--export', dest='export_format', default='', help='Export after training (onnx, engine, ...)')
    train_parser.add_argument('--dedupe-val', action='store_true', help='Remove val files duplicated in train folders')
    train_parser.set_defaults(func=run_train_command)

    export_parser = subparsers.add_parser('export', help='Export trained best.pt weights')
    export_parser.add_argument('--config', '-c', required=True, help='Training run name (YAML name without .yaml)')
    export_parser.add_argument('--weights', '-w', default='', help='Custom weights path (default: best.pt from runs)')
    export_parser.add_argument('--export', '-f', dest='export_format', default='onnx', help='Export format')
    export_parser.add_argument('--device', default='auto')
    export_parser.add_argument('--task', default=DEFAULT_TASK)
    export_parser.set_defaults(func=run_export_command)

    return parser


def run_train_command(args: argparse.Namespace) -> None:
    export_format = args.export_format.strip() or None
    train_model(
        config_name=args.config,
        base_model=args.base_model,
        epochs=args.epochs,
        img_size=args.imgsz,
        batch=args.batch,
        device=resolve_device(args.device),
        task=args.task,
        export_format=export_format,
        dedupe_val=args.dedupe_val,
    )


def run_export_command(args: argparse.Namespace) -> None:
    weights = Path(args.weights) if args.weights else best_weights_path(args.config, args.task)
    if not weights.is_file():
        raise FileNotFoundError(f'Weights not found: {weights}')
    export_weights(weights, args.export_format, resolve_device(args.device))


def main(argv: Optional[list[str]] = None) -> int:
    setup_directories()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except (FileNotFoundError, ValueError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('\nInterrupted.', file=sys.stderr)
        return 130
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
