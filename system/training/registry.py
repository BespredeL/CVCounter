# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

""" Registry of built-in training providers. """

from __future__ import annotations

import importlib
import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from system.training.base import BaseTrainingProvider, TrainingRequest, TrainingResult

DEFAULT_TRAINING_PROVIDER = 'ultralytics'


@dataclass(frozen=True)
class BuiltinTrainingProvider:
    """Declarative metadata for a built-in training provider."""

    id: str
    aliases: tuple[str, ...]
    module: str
    class_name: str
    dependencies: tuple[str, ...]
    tasks: tuple[str, ...]
    dataset_formats: tuple[str, ...]
    export_formats: tuple[str, ...]
    architectures: tuple[str, ...] = ()
    optional_dependencies: tuple[str, ...] = ()
    install_provider: str = ''
    supports_training: bool = True
    supports_finetuning: bool = True
    supports_export: bool = False
    supports_validation: bool = False


_BUILTIN_TRAINING_PROVIDERS = (
    BuiltinTrainingProvider(
        'ultralytics',
        ('ultralytics', 'yolo'),
        'system.training.ultralytics_provider',
        'UltralyticsTrainingProvider',
        ('torch', 'ultralytics'),
        ('detect', 'segment', 'classify', 'pose'),
        ('yolo',),
        ('onnx', 'engine'),
        ('yolo',),
        install_provider='ultralytics',
        supports_training=True,
        supports_finetuning=True,
        supports_export=True,
        supports_validation=True,
    ),
    BuiltinTrainingProvider(
        'torchvision',
        ('torchvision', 'torchvision_detection'),
        'system.training.torchvision_provider',
        'TorchVisionTrainingProvider',
        ('torch', 'torchvision'),
        ('detect',),
        ('coco',),
        (),
        ('fasterrcnn',),
        install_provider='pytorch',
        supports_training=True,
        supports_finetuning=True,
        supports_export=False,
        supports_validation=True,
    ),
    BuiltinTrainingProvider(
        'rf_detr',
        ('rf_detr', 'rfdetr', 'rf-detr'),
        'system.training.adapters.rf_detr_trainer',
        'RFDETRTrainingProvider',
        ('torch', 'rfdetr'),
        ('detect',),
        ('coco', 'yolo'),
        (),
        ('rf_detr',),
        install_provider='rfdetr',
        supports_training=True,
        supports_finetuning=True,
        supports_export=False,
        supports_validation=False,
    ),
    BuiltinTrainingProvider(
        'd_fine',
        ('d_fine', 'dfine', 'd-fine'),
        'system.training.adapters.d_fine_trainer',
        'DFINETrainingProvider',
        ('torch',),
        ('detect',),
        ('coco', 'yolo'),
        (),
        ('d_fine',),
        install_provider='pytorch',
        supports_training=False,
        supports_finetuning=False,
        supports_export=False,
        supports_validation=False,
    ),
    BuiltinTrainingProvider(
        'rtmdet',
        ('rtmdet', 'rtm-det'),
        'system.training.adapters.rtmdet_trainer',
        'RTMDetTrainingProvider',
        ('torch', 'mmdet'),
        ('detect',),
        ('coco', 'yolo'),
        (),
        ('rtmdet',),
        install_provider='mmdet',
        supports_training=False,
        supports_finetuning=False,
        supports_export=False,
        supports_validation=False,
    ),
)
_TRAINING_PROVIDER_BY_ALIAS = {
    alias: provider
    for provider in _BUILTIN_TRAINING_PROVIDERS
    for alias in provider.aliases
}
_INSTANCES: dict[str, BaseTrainingProvider] = {}


def _has_dependency(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def training_provider_ids() -> list[str]:
    """Return every declared training provider id."""
    return [provider.id for provider in _BUILTIN_TRAINING_PROVIDERS]


def resolve_provider_id(provider: Optional[str]) -> str:
    """
    Resolve a provider alias to its canonical id.

    Args:
        provider (Optional[str]): Requested provider id or alias

    Returns:
        str: Canonical provider id
    """
    normalized = (provider or DEFAULT_TRAINING_PROVIDER).strip().lower()
    resolved = _TRAINING_PROVIDER_BY_ALIAS.get(normalized)
    if resolved is None:
        supported = ', '.join(training_provider_ids())
        raise ValueError(f"Unknown training provider '{provider}'. Supported providers: {supported}")
    return resolved.id


def get_provider_definition(provider: Optional[str]) -> BuiltinTrainingProvider:
    """Return the declarative metadata for a provider alias."""
    normalized = (provider or DEFAULT_TRAINING_PROVIDER).strip().lower()
    definition = _TRAINING_PROVIDER_BY_ALIAS.get(normalized)
    if definition is None:
        supported = ', '.join(training_provider_ids())
        raise ValueError(f"Unknown training provider '{provider}'. Supported providers: {supported}")
    return definition


def get_provider_status(provider: Optional[str]) -> dict[str, Any]:
    """
    Report dependency health and declared capabilities for one training provider.

    Args:
        provider (Optional[str]): Provider id or alias

    Returns:
        dict[str, Any]: Status payload
    """
    definition = get_provider_definition(provider)
    dependency_status = {name: _has_dependency(name) for name in definition.dependencies}
    optional_status = {name: _has_dependency(name) for name in definition.optional_dependencies}
    missing = [name for name, installed in dependency_status.items() if not installed]

    if not definition.supports_training:
        status = 'unavailable'
        error = f"Training for '{definition.id}' is not yet implemented (planned for future release)."
        available = False
    elif missing:
        status = 'unavailable'
        error = f"Missing dependencies: {', '.join(missing)}"
        available = False
    else:
        status = 'available'
        error = None
        available = True
        try:
            load_provider(definition.id, check_dependencies=False)
        except Exception as exc:
            status = 'error'
            error = str(exc)
            available = False

    model_catalog_available = False
    try:
        prov = load_provider(definition.id, check_dependencies=False)
        model_catalog_available = bool(prov.curated_models())
    except Exception:
        model_catalog_available = False

    inference_supported = False
    adapter_registered = False
    backend_available = _has_dependency('torch')
    if definition.id == 'torchvision':
        inference_supported = bool(_has_dependency('torchvision'))
        adapter_registered = True
        backend_available = bool(_has_dependency('torch'))
    else:
        try:
            from system.detection.registry import get_provider_status as get_det_status, is_backend_available
            det_available = bool(is_backend_available(definition.id))
            det_status = get_det_status(definition.id)
            inference_supported = det_available and bool(det_status.get("inference_available", False))
            adapter_registered = bool(det_status.get("adapter_registered", False))
            backend_available = bool(det_status.get("backend_available", _has_dependency('torch')))
        except Exception:
            inference_supported = False
            adapter_registered = False
            backend_available = False

    return {
        'id': definition.id,
        'aliases': list(definition.aliases),
        'status': status,
        'available': available,
        'training_available': available,
        'training_supported': definition.supports_training,
        'architecture_registered': True,
        'adapter_registered': adapter_registered,
        'backend_available': backend_available,
        'inference_available': inference_supported,
        'inference_supported': inference_supported,
        'model_catalog_available': model_catalog_available,
        'install_provider': definition.install_provider,
        'supports_training': definition.supports_training,
        'supports_finetuning': definition.supports_finetuning,
        'supports_export': definition.supports_export,
        'supports_validation': definition.supports_validation,
        'export_formats': definition.export_formats,
        'dependencies': dependency_status,
        'optional_dependencies': optional_status,
        'capabilities': {
            'tasks': list(definition.tasks),
            'architectures': list(definition.architectures),
            'dataset_formats': list(definition.dataset_formats),
            'export_formats': list(definition.export_formats),
            'supports_training': definition.supports_training,
            'supports_finetuning': definition.supports_finetuning,
            'supports_export': definition.supports_export,
            'supports_validation': definition.supports_validation,
            'architecture_registered': True,
            'adapter_registered': adapter_registered,
            'backend_available': backend_available,
            'model_catalog_available': model_catalog_available,
            'inference_available': inference_supported,
            'inference_supported': inference_supported,
            'training_supported': definition.supports_training,
            'training_available': available,
        },
        'error': error,
    }


def get_provider_statuses() -> list[dict[str, Any]]:
    """Return independent health and capability information for every training provider."""
    return [get_provider_status(provider.id) for provider in _BUILTIN_TRAINING_PROVIDERS]


def load_provider(provider: Optional[str], check_dependencies: bool = False) -> BaseTrainingProvider:
    """
    Import and instantiate a training provider.

    Args:
        provider (Optional[str]): Provider id or alias
        check_dependencies (bool): Whether to enforce dependency checks before returning instance

    Returns:
        BaseTrainingProvider: The provider instance
    """
    definition = get_provider_definition(provider)
    cached = _INSTANCES.get(definition.id)
    if cached is not None and not check_dependencies:
        return cached

    if check_dependencies:
        if not definition.supports_training:
            raise RuntimeError(
                f"Training provider '{definition.id}' is unavailable; training is not yet implemented."
            )
        missing = [name for name in definition.dependencies if not _has_dependency(name)]
        if missing:
            raise RuntimeError(
                f"Training provider '{definition.id}' is unavailable; "
                f"missing dependencies: {', '.join(missing)}. "
                f"Install them with `python install.py --provider {definition.install_provider}`."
            )

    try:
        module = importlib.import_module(definition.module)
        instance = getattr(module, definition.class_name)()
    except Exception as exc:
        raise RuntimeError(f"Training provider '{definition.id}' failed to load: {exc}") from exc

    _INSTANCES[definition.id] = instance
    return instance


def resolve_training_provider(
        provider: Optional[str],
        task: str = 'detect',
        dataset_format: Optional[str] = None,
) -> str:
    """
    Pick the provider that can train this task from this dataset format.

    Args:
        provider (Optional[str]): Requested provider, or 'auto'
        task (str): Training task
        dataset_format (Optional[str]): Exported dataset format

    Returns:
        str: Canonical provider id
    """
    normalized = (provider or DEFAULT_TRAINING_PROVIDER).strip().lower()
    if normalized not in ('', 'auto', 'default'):
        return resolve_provider_id(normalized)

    for definition in _BUILTIN_TRAINING_PROVIDERS:
        if task not in definition.tasks:
            continue
        if dataset_format and dataset_format not in definition.dataset_formats:
            continue
        return definition.id
    raise ValueError(
        f"No training provider can train task '{task}' from dataset format "
        f"'{dataset_format or 'any'}'"
    )


def check_training_compatibility(
        provider: Optional[str],
        task: str = 'detect',
        dataset_format: Optional[str] = None,
        export_format: Optional[str] = None,
) -> dict[str, Any]:
    """
    Compare a training job against the capabilities a provider declares.

    Args:
        provider (Optional[str]): Provider id or alias
        task (str): Training task
        dataset_format (Optional[str]): Dataset export format
        export_format (Optional[str]): Post-training export format

    Returns:
        dict[str, Any]: Compatibility report with the reasons for any mismatch
    """
    definition = get_provider_definition(provider)
    reasons = []
    if task not in definition.tasks:
        reasons.append(f"Task '{task}' is not declared by this provider")
    if dataset_format and dataset_format not in definition.dataset_formats:
        reasons.append(f"Dataset format '{dataset_format}' is not consumed by this provider")
    if export_format and export_format not in definition.export_formats:
        reasons.append(f"Export format '{export_format}' is not produced by this provider")
    return {
        'provider': definition.id,
        'compatible': not reasons,
        'reasons': reasons,
    }


def provider_paths(
        provider: Optional[str],
        project_root: Optional[Path | str] = None,
) -> tuple[Path, Path, Path]:
    """
    Resolve the cfg/models/runs directories owned by a training provider.

    Args:
        provider (Optional[str]): Provider id or alias
        project_root (Optional[Path | str]): Project root override

    Returns:
        tuple[Path, Path, Path]: cfg, models and runs directories
    """
    from system.utils.paths import resolve_provider_training_paths

    definition = get_provider_definition(provider)
    return resolve_provider_training_paths(definition.id, project_root)


RUN_WEIGHT_NAMES = (
    'weights/best.pt',
    'weights/model_final.pt',
    'weights/best.pth',
    'weights/model_final.pth',
)


def list_runs(
        provider: Optional[str] = None,
        task: str = 'detect',
        project_root: Optional[Path | str] = None,
) -> list[dict[str, Any]]:
    """
    List finished runs of a provider without importing its framework.

    Args:
        provider (Optional[str]): Provider id or alias
        task (str): Task folder inside the runs directory
        project_root (Optional[Path | str]): Project root override

    Returns:
        list[dict[str, Any]]: Run descriptors
    """
    definition = get_provider_definition(provider)
    task_dir = provider_paths(definition.id, project_root)[2] / task
    if not task_dir.is_dir():
        return []

    runs = []
    for path in sorted(task_dir.iterdir(), reverse=True):
        for candidate in RUN_WEIGHT_NAMES:
            weights = path / candidate
            if weights.is_file():
                runs.append({
                    'provider': definition.id,
                    'name': path.name,
                    'task': task,
                    'weights': str(weights),
                    'mtime': weights.stat().st_mtime,
                })
                break
    return runs


def find_run_weights(
        run_name: str,
        task: str = 'detect',
        provider: Optional[str] = None,
        project_root: Optional[Path | str] = None,
) -> Optional[Path]:
    """
    Locate the primary checkpoint of one finished run.

    Args:
        run_name (str): Name of the training run
        task (str): Task folder inside the runs directory
        provider (Optional[str]): Provider id or alias
        project_root (Optional[Path | str]): Project root override

    Returns:
        Optional[Path]: The checkpoint path when it exists
    """
    definition = get_provider_definition(provider)
    run_dir = provider_paths(definition.id, project_root)[2] / task / run_name.removesuffix('.yaml')
    for candidate in RUN_WEIGHT_NAMES:
        weights = run_dir / candidate
        if weights.is_file():
            return weights
    return None


__all__ = [
    'BuiltinTrainingProvider',
    'DEFAULT_TRAINING_PROVIDER',
    'TrainingRequest',
    'TrainingResult',
    'check_training_compatibility',
    'find_run_weights',
    'get_provider_definition',
    'get_provider_status',
    'get_provider_statuses',
    'list_runs',
    'load_provider',
    'provider_paths',
    'resolve_provider_id',
    'resolve_training_provider',
    'training_provider_ids',
]
