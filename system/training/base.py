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

    def curated_models(self) -> dict[str, Any]:
        """Return the provider's downloadable start checkpoints by filename."""
        return getattr(self, "BASE_MODELS", {})

    def base_models(self) -> list[dict[str, Any]]:
        """Return the base checkpoints this provider can start from."""
        models_dir = self.models_dir()
        catalog: list[dict[str, Any]] = []
        curated = self.curated_models()
        installed_files: dict[str, Path] = {}
        if models_dir.is_dir():
            for p in sorted(models_dir.glob("*.*")):
                if p.is_file() and p.suffix.lower() in (".pth", ".pt", ".onnx", ".engine"):
                    installed_files[p.name] = p

        try:
            shared_dir = self.models_dir().parent.parent / "models"
            if shared_dir.is_dir():
                for p in sorted(shared_dir.glob("*.*")):
                    if p.is_file() and p.name not in installed_files and p.suffix.lower() in (".pth", ".pt", ".onnx", ".engine"):
                        installed_files[p.name] = p
        except Exception:
            pass

        for name, info in curated.items():
            is_installed = name in installed_files
            size_mb = (
                round(installed_files[name].stat().st_size / (1024 * 1024), 1)
                if is_installed else info.get("size_mb", 0.0)
            )
            catalog.append({
                "name": name,
                "display_name": info.get("name", name),
                "task": info.get("task", "detect"),
                "task_type": info.get("task", "detect"),
                "size_mb": size_mb,
                "speed": info.get("speed", "Fast"),
                "recommended": info.get("recommended", False),
                "description": info.get("description", ""),
                "installed": is_installed,
                "path": str(installed_files[name]) if is_installed else None,
            })

        for name, p_file in installed_files.items():
            if name not in curated:
                size_mb = round(p_file.stat().st_size / (1024 * 1024), 1)
                catalog.append({
                    "name": name,
                    "display_name": f"Custom: {name}",
                    "task": "detect",
                    "task_type": "detect",
                    "size_mb": size_mb,
                    "speed": "Custom",
                    "recommended": False,
                    "description": "Custom model found in the models directory.",
                    "installed": True,
                    "path": str(p_file),
                })
        return catalog

    def supports_base_model(self, model_name: str) -> bool:
        """
        Whether this provider can fetch a checkpoint of this name.

        Args:
            model_name (str): Checkpoint filename

        Returns:
            bool: True when the name is in the downloadable catalog
        """
        clean = Path(model_name).name
        return clean in self.curated_models()

    def download_base_model(self, model_name: str, progress_callback=None) -> Path:
        """
        Fetch a base checkpoint into the provider model directory.

        Args:
            model_name (str): The checkpoint name
            progress_callback: Optional callback receiving progress dicts

        Returns:
            Path: The local checkpoint path
        """
        from system.utils.downloads import download_file

        clean_name = Path(model_name).name
        curated = self.curated_models()
        info = curated.get(clean_name)
        if info is None or not info.get("url"):
            raise ValueError(
                f"Unknown base model '{clean_name}' for provider '{self.id}'. Supported: {', '.join(curated)}"
            )

        urls = info["url"] if isinstance(info["url"], (list, tuple)) else [info["url"]]
        dest = self.models_dir() / clean_name
        return download_file(urls, dest, clean_name, progress_callback)

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
