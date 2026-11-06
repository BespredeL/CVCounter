# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

"""
Standalone CLI to train and export models through the project training providers.

This script is intentionally independent from the web app: it trains from the
artifacts already on disk (a YOLO data.yaml or a COCO JSON export) instead of
re-exporting a dataset from the annotation store.

Examples:
    python train.py providers
    python train.py list --provider ultralytics
    python train.py train --config road-map --epochs 200 --export onnx
    python train.py train --config road-map --provider torchvision --dataset-format coco --epochs 5
    python train.py export --config road-map --export engine
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

import yaml

import system.utils.ultralytics_home

from system.managers.training_job_manager import (
    DEFAULT_EPOCHS,
    DEFAULT_IMG_SIZE,
    DEFAULT_TASK,
    training_job_manager,
)
from system.training.base import TrainingRequest
from system.training.registry import (
    check_training_compatibility,
    get_provider_definition,
    load_provider,
    provider_paths,
    resolve_training_provider,
)

PROJECT_ROOT = Path(__file__).resolve().parent
DATASETS_DIR = PROJECT_ROOT / 'storage' / 'datasets'


def _print_progress(payload: dict) -> None:
    """
    Render a provider progress event on the console.

    Args:
        payload (dict): Progress event emitted by the provider
    """
    event = payload.get('event')
    if event == 'epoch_end':
        metrics = payload.get('metrics') or {}
        detail = ' '.join(f'{key}={value:.4f}' if isinstance(value, float) else f'{key}={value}'
                          for key, value in metrics.items())
        print(f"  epoch {payload.get('epoch')}/{payload.get('epochs')} {detail}")
    elif event == 'log':
        print(f"  {payload.get('message')}")
    elif event in ('start', 'complete', 'exported'):
        print(f"{event}: {payload}")
    elif payload.get('status') == 'downloading':
        print(f"  downloading {payload.get('model')}: {payload.get('percent')}%", end='\r')


def list_configs(provider: Optional[str]) -> None:
    """
    Print the training artifacts a provider can start from.

    Args:
        provider (Optional[str]): Provider id or alias
    """
    definition = get_provider_definition(provider)
    dataset_format = definition.dataset_formats[0]
    if dataset_format == 'coco':
        found = sorted(
            path.parent.parent.parent.name for path in DATASETS_DIR.glob('*/coco/annotations/instances_train.json')
        ) if DATASETS_DIR.is_dir() else []
        label = 'COCO datasets (storage/datasets/<name>/coco)'
    else:
        cfg_dir = provider_paths(definition.id)[0]
        found = sorted(path.stem for path in cfg_dir.glob('*.yaml')) if cfg_dir.is_dir() else []
        label = f'dataset configs in {cfg_dir}'
    if not found:
        print(f'No {label} found')
        return
    print(f'{definition.id} ({dataset_format}) can train:')
    for name in found:
        print(f'  - {name}')


def print_providers() -> None:
    """Print every training provider with its availability and capabilities."""
    for status in training_job_manager.provider_statuses():
        capabilities = status['capabilities']
        flag = 'available' if status['available'] else f"unavailable ({status['error']})"
        print(f"{status['id']} [{flag}]")
        print(f"  tasks: {', '.join(capabilities['tasks'])}")
        print(f"  dataset formats: {', '.join(capabilities['dataset_formats'])}")
        print(f"  export formats: {', '.join(capabilities['export_formats']) or 'none'}")


def _request_from_yaml(config_name: str, args: argparse.Namespace, provider_id: str) -> TrainingRequest:
    """
    Build a request for a provider that consumes a YOLO data.yaml export.

    Args:
        config_name (str): Config name without .yaml
        args (argparse.Namespace): Parsed CLI arguments
        provider_id (str): Canonical provider id

    Returns:
        TrainingRequest: The request to run
    """
    cfg_dir = provider_paths(provider_id)[0]
    data_yaml = cfg_dir / f'{config_name.removesuffix(".yaml")}.yaml'
    if not data_yaml.is_file():
        raise FileNotFoundError(f'Dataset config not found: {data_yaml}')

    with open(data_yaml, encoding='utf-8') as file:
        data = yaml.safe_load(file) or {}
    raw_path = data.get('path')
    if not raw_path:
        raise ValueError(f"Cannot resolve the dataset: 'path' is missing in {data_yaml}")
    dataset_root = Path(raw_path)
    if not dataset_root.is_absolute():
        dataset_root = (data_yaml.parent / dataset_root).resolve()
    if not dataset_root.is_dir():
        raise FileNotFoundError(f'Dataset directory not found: {dataset_root}')

    classes = [str(data['names'][key]) for key in sorted(data.get('names') or {})]
    print(f'Training {config_name} with provider {provider_id}')
    print(f'  data: {data_yaml}')
    print(f'  dataset: {dataset_root}')
    return TrainingRequest(
        config_name=config_name,
        dataset_name=config_name,
        dataset_root=dataset_root,
        dataset_format='yolo',
        dataset_paths={'yaml': str(data_yaml)},
        classes=tuple(classes),
        task=args.task,
        base_model=args.base_model or training_job_manager.default_base_model(provider_id),
        epochs=args.epochs,
        img_size=args.imgsz,
        batch=args.batch,
        device=args.device,
        provider=provider_id,
        export_format=args.export_format.strip() or None,
        project_root=PROJECT_ROOT,
        options={'dedupe_val': bool(args.dedupe_val)},
        progress_callback=_print_progress,
    )


def _request_from_coco(config_name: str, args: argparse.Namespace, provider_id: str) -> TrainingRequest:
    """
    Build a request for a provider that consumes a COCO JSON export.

    Args:
        config_name (str): Dataset name under storage/datasets
        args (argparse.Namespace): Parsed CLI arguments
        provider_id (str): Canonical provider id

    Returns:
        TrainingRequest: The request to run
    """
    dataset_root = DATASETS_DIR / config_name
    annotations = dataset_root / 'coco' / 'annotations'
    split_paths = {split: annotations / f'instances_{split}.json' for split in ('train', 'val')}
    for split, path in split_paths.items():
        if not path.is_file():
            raise FileNotFoundError(
                f"{path} not found; export the dataset as COCO first (Datasets -> {config_name} -> Train)"
            )

    with open(split_paths['train'], encoding='utf-8') as file:
        payload = json.load(file)
    categories = sorted(payload.get('categories') or [], key=lambda entry: entry['id'])
    classes = tuple(str(entry['name']) for entry in categories)

    print(f'Training {config_name} with provider {provider_id}')
    print(f'  dataset: {dataset_root}')
    print(f'  annotations: {annotations}')
    return TrainingRequest(
        config_name=config_name,
        dataset_name=config_name,
        dataset_root=dataset_root,
        dataset_format='coco',
        dataset_paths={split: str(path) for split, path in split_paths.items()},
        classes=classes,
        task=args.task,
        base_model=args.base_model or training_job_manager.default_base_model(provider_id),
        epochs=args.epochs,
        img_size=args.imgsz,
        batch=args.batch,
        device=args.device,
        provider=provider_id,
        export_format=args.export_format.strip() or None,
        project_root=PROJECT_ROOT,
        options={'dedupe_val': bool(args.dedupe_val)},
        progress_callback=_print_progress,
    )


def build_cli_request(args: argparse.Namespace) -> TrainingRequest:
    """
    Turn CLI arguments into a framework-neutral training request.

    Args:
        args (argparse.Namespace): Parsed CLI arguments

    Returns:
        TrainingRequest: The validated request
    """
    provider_id = resolve_training_provider(args.provider, args.task, args.dataset_format)
    definition = get_provider_definition(provider_id)
    dataset_format = (args.dataset_format or definition.dataset_formats[0]).strip().lower()
    export_format = args.export_format.strip()
    report = check_training_compatibility(provider_id, args.task, dataset_format, export_format or None)
    if not report['compatible']:
        raise ValueError('; '.join(report['reasons']))
    if dataset_format == 'coco':
        return _request_from_coco(args.config, args, provider_id)
    return _request_from_yaml(args.config, args, provider_id)


def run_train_command(args: argparse.Namespace) -> None:
    """
    Run a training job from the CLI.

    Args:
        args (argparse.Namespace): Parsed CLI arguments
    """
    request = build_cli_request(args)
    instance = load_provider(request.provider)
    instance.prepare(request)
    result = instance.train(request)
    print(f'Training complete: {result.weights}')
    if result.exported:
        print(f'Exported: {result.exported}')


def run_export_command(args: argparse.Namespace) -> None:
    """
    Export a finished run through the provider that trained it.

    Args:
        args (argparse.Namespace): Parsed CLI arguments
    """
    provider_id = resolve_training_provider(args.provider, args.task, None)
    exported = training_job_manager.export_run(
        args.config,
        args.export_format,
        args.task,
        args.device,
        provider_id,
        Path(args.weights) if args.weights else None,
    )
    print(f'Export complete: {exported}')


def build_parser() -> argparse.ArgumentParser:
    """Return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description='Standalone train/export CLI for the project training providers.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            'Project layout:\n'
            '  config/<provider>/cfg/       dataset configs (.yaml)\n'
            '  config/<provider>/models/    base checkpoints\n'
            '  config/<provider>/runs/      training output\n'
            '  storage/datasets/            images, labels and COCO exports\n'
        ),
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    providers_parser = subparsers.add_parser('providers', help='List training providers and their capabilities')
    providers_parser.set_defaults(func=lambda args: print_providers())

    list_parser = subparsers.add_parser('list', help='List training artifacts a provider can start from')
    list_parser.add_argument('--provider', '-p', default=None)
    list_parser.set_defaults(func=lambda args: list_configs(args.provider))

    train_parser = subparsers.add_parser('train', help='Train a model from a base checkpoint')
    train_parser.add_argument('--config', '-c', required=True, help='Dataset name or config name without .yaml')
    train_parser.add_argument('--provider', '-p', default='auto', help='Training provider (auto = pick by format/task)')
    train_parser.add_argument('--dataset-format', default='', help='Dataset format (default: the provider format)')
    train_parser.add_argument('--base-model', '-m', default='', help='Base checkpoint (default: provider recommendation)')
    train_parser.add_argument('--epochs', '-e', type=int, default=DEFAULT_EPOCHS)
    train_parser.add_argument('--imgsz', type=int, default=DEFAULT_IMG_SIZE)
    train_parser.add_argument('--batch', type=int, default=-1, help='Batch size (-1 = provider default)')
    train_parser.add_argument('--device', default='auto', help='cuda device id, cpu, or auto')
    train_parser.add_argument('--task', default=DEFAULT_TASK)
    train_parser.add_argument('--export', dest='export_format', default='', help='Export after training (onnx, engine)')
    train_parser.add_argument('--dedupe-val', action='store_true', help='Remove val files duplicated in train folders')
    train_parser.set_defaults(func=run_train_command)

    export_parser = subparsers.add_parser('export', help='Export the weights of a finished run')
    export_parser.add_argument('--config', '-c', required=True, help='Training run name')
    export_parser.add_argument('--provider', '-p', default='auto', help='Provider that trained the run')
    export_parser.add_argument('--weights', '-w', default='', help='Custom weights path (default: run weights)')
    export_parser.add_argument('--export', '-f', dest='export_format', default='onnx', help='Export format')
    export_parser.add_argument('--device', default='auto')
    export_parser.add_argument('--task', default=DEFAULT_TASK)
    export_parser.set_defaults(func=run_export_command)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """
    Run the CLI.

    Args:
        argv (Optional[list[str]]): Argument vector; defaults to sys.argv

    Returns:
        int: Process exit code
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except (FileNotFoundError, ValueError, RuntimeError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('\nInterrupted.', file=sys.stderr)
        return 130
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
