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
    ),
    BuiltinTrainingProvider(
        'torchvision',
        ('torchvision', 'torchvision_detection'),
        'system.training.torchvision_provider',
        'TorchVisionTrainingProvider',
        ('torch', 'torchvision'),
        ('detect',),
        ('coco',),
        ('onnx',),
        ('fasterrcnn',),
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
    error = f"Missing dependencies: {', '.join(missing)}" if missing else None
    status = 'unavailable' if missing else 'available'

    if not missing:
        try:
            load_provider(definition.id)
        except Exception as exc:
            status = 'error'
            error = str(exc)

    return {
        'id': definition.id,
        'aliases': list(definition.aliases),
        'status': status,
        'available': status == 'available',
        'dependencies': dependency_status,
        'optional_dependencies': optional_status,
        'capabilities': {
            'tasks': list(definition.tasks),
            'architectures': list(definition.architectures),
            'dataset_formats': list(definition.dataset_formats),
            'export_formats': list(definition.export_formats),
        },
        'error': error,
    }


def get_provider_statuses() -> list[dict[str, Any]]:
    """Return independent health and capability information for every training provider."""
    return [get_provider_status(provider.id) for provider in _BUILTIN_TRAINING_PROVIDERS]


def load_provider(provider: Optional[str]) -> BaseTrainingProvider:
    """
    Import and instantiate a training provider.

    Args:
        provider (Optional[str]): Provider id or alias

    Returns:
        BaseTrainingProvider: The provider instance
    """
    definition = get_provider_definition(provider)
    cached = _INSTANCES.get(definition.id)
    if cached is not None:
        return cached

    missing = [name for name in definition.dependencies if not _has_dependency(name)]
    if missing:
        raise RuntimeError(
            f"Training provider '{definition.id}' is unavailable; "
            f"missing dependencies: {', '.join(missing)}. "
            f"Install them with `python install.py --provider {definition.id}`."
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


__all__ = [
    'BuiltinTrainingProvider',
    'DEFAULT_TRAINING_PROVIDER',
    'TrainingRequest',
    'TrainingResult',
    'check_training_compatibility',
    'get_provider_definition',
    'get_provider_status',
    'get_provider_statuses',
    'load_provider',
    'provider_paths',
    'resolve_provider_id',
    'resolve_training_provider',
    'training_provider_ids',
]
