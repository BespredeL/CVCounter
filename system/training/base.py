# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

"""Framework-neutral contracts shared by every training provider."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional


class TrainingCancelledError(RuntimeError):
    """Raised when training is cancelled by the user."""


def resolve_torch_device(device: Optional[str]) -> str | int:
    """
    Resolve a torch device specifier.

    Args:
        device (Optional[str]): Requested device, e.g. 'auto', '0', 'cpu'

    Returns:
        str | int: Device value accepted by torch and by provider trainers
    """
    try:
        import torch
        cuda_ok = torch.cuda.is_available()
    except ImportError:
        cuda_ok = False

    if device is None or str(device).lower() == 'auto':
        return 0 if cuda_ok else 'cpu'
    if str(device).isdigit():
        return int(device)
    return device


@dataclass(frozen=True)
class TrainingRequest:
    """A single training job described without reference to any framework."""

    config_name: str
    dataset_name: str
    dataset_root: Path
    dataset_format: str
    dataset_paths: dict[str, Any]
    classes: tuple[str, ...]
    task: str
    base_model: str
    epochs: int
    img_size: int
    batch: int
    device: str | int
    provider: str = ''
    export_format: Optional[str] = None
    project_root: Optional[Path] = None
    run_dir: Optional[Path] = None
    options: dict[str, Any] = field(default_factory=dict)
    progress_callback: Optional[Callable[[dict], None]] = None
    cancel_check: Optional[Callable[[], bool]] = None

    @property
    def run_name(self) -> str:
        """Stable artifact name for this request."""
        return (self.config_name or self.dataset_name).removesuffix('.yaml')


@dataclass
class TrainingResult:
    """What a provider returns when a training run finishes."""

    weights: Path
    run_dir: Optional[Path] = None
    exported: Optional[Path] = None
    metrics: dict[str, Any] = field(default_factory=dict)


class BaseTrainingProvider(ABC):
    """Contract every training provider implements."""

    id: str = ''
    tasks: tuple[str, ...] = ()
    dataset_formats: tuple[str, ...] = ()
    export_formats: tuple[str, ...] = ()

    def resolve_device(self, device: Optional[str]) -> str | int:
        """
        Resolve the training device.

        Args:
            device (Optional[str]): Requested device

        Returns:
            str | int: Resolved device
        """
        return resolve_torch_device(device)

    def directories(self, project_root: Optional[Path | str] = None) -> tuple[Path, Path, Path]:
        """
        Resolve the cfg/models/runs directories this provider owns.

        Args:
            project_root (Optional[Path | str]): Project root override

        Returns:
            tuple[Path, Path, Path]: cfg, models and runs directories
        """
        from system.utils.paths import resolve_provider_training_paths

        return resolve_provider_training_paths(self.id, project_root)

    def models_dir(self, project_root: Optional[Path | str] = None) -> Path:
        """Directory holding the starting checkpoints of this provider."""
        return self.directories(project_root)[1]

    def runs_dir(self, project_root: Optional[Path | str] = None) -> Path:
        """Directory holding the training artifacts of this provider."""
        return self.directories(project_root)[2]

    def base_models(self) -> list[dict[str, Any]]:
        """Return the base checkpoints this provider can start from."""
        return []

    def curated_models(self) -> dict[str, Any]:
        """Return the provider's downloadable start checkpoints by filename."""
        return {}

    def supports_base_model(self, model_name: str) -> bool:
        """
        Whether this provider can fetch a checkpoint of this name.

        Args:
            model_name (str): Checkpoint filename

        Returns:
            bool: True when the name is in the downloadable catalog
        """
        return model_name in self.curated_models()

    def download_base_model(self, model_name: str, progress_callback=None) -> Path:
        """
        Fetch a base checkpoint into the provider model directory.

        Args:
            model_name (str): The checkpoint name
            progress_callback: Optional callback receiving progress dicts

        Returns:
            Path: The local checkpoint path
        """
        raise NotImplementedError(f"Provider '{self.id}' does not offer downloadable base models")

    def prepare(self, request: TrainingRequest) -> None:
        """
        Validate a request before any training artifact is written.

        Args:
            request (TrainingRequest): The job to validate

        Returns:
            None
        """
        if request.task not in self.tasks:
            raise ValueError(
                f"Provider '{self.id}' does not train task '{request.task}'; "
                f"supported tasks: {', '.join(self.tasks)}"
            )
        if request.dataset_format not in self.dataset_formats:
            raise ValueError(
                f"Provider '{self.id}' does not consume '{request.dataset_format}' datasets; "
                f"supported formats: {', '.join(self.dataset_formats)}. Export the dataset again "
                'in a supported format.'
            )
        if request.export_format and request.export_format not in self.export_formats:
            raise ValueError(
                f"Provider '{self.id}' cannot export to '{request.export_format}'; "
                f"supported formats: {', '.join(self.export_formats) or 'none'}"
            )

    @abstractmethod
    def train(self, request: TrainingRequest) -> TrainingResult:
        """
        Run training and return the resulting artifacts.

        Args:
            request (TrainingRequest): The job to run

        Returns:
            TrainingResult: Weights and metrics
        """

    def export(self, weights: Path, export_format: str, device: str | int) -> Path:
        """
        Export trained weights into a deployable format.

        Args:
            weights (Path): Trained checkpoint
            export_format (str): Requested format
            device (str | int): Export device

        Returns:
            Path: The exported artifact
        """
        raise NotImplementedError(
            f"Provider '{self.id}' does not implement '{export_format}' export"
        )
