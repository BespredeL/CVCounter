# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

""" Ultralytics training provider: fine-tunes and exports YOLO models. """

from __future__ import annotations

from pathlib import Path
from typing import Any

from system.training.base import BaseTrainingProvider, TrainingRequest, TrainingResult


class UltralyticsTrainingProvider(BaseTrainingProvider):
    """Train models with the Ultralytics framework from a YOLO dataset export."""

    id = 'ultralytics'
    tasks = ('detect', 'segment', 'classify', 'pose')
    dataset_formats = ('yolo',)
    export_formats = ('onnx', 'engine')

    def prepare(self, request: TrainingRequest) -> None:
        """
        Validate that a YOLO data.yaml export is present.

        Args:
            request (TrainingRequest): The job to validate

        Returns:
            None
        """
        super().prepare(request)
        yaml_path = request.dataset_paths.get('yaml')
        if not yaml_path:
            raise ValueError(
                "Ultralytics training needs a data.yaml export; export the dataset as 'yolo' first"
            )
        if not Path(yaml_path).is_file():
            raise FileNotFoundError(f'Dataset config not found: {yaml_path}')

    def train(self, request: TrainingRequest) -> TrainingResult:
        """
        Run an Ultralytics training job.

        Args:
            request (TrainingRequest): The job to run

        Returns:
            TrainingResult: Trained weights and optional export
        """
        from system.training import yolo_trainer

        self.prepare(request)
        yolo_trainer.setup_directories(request.project_root)

        config_name = Path(request.dataset_paths['yaml']).stem
        device = self.resolve_device(str(request.device))
        weights = yolo_trainer.train_model(
            config_name=config_name,
            base_model=request.base_model,
            epochs=request.epochs,
            img_size=request.img_size,
            batch=request.batch,
            device=device,
            task=request.task,
            export_format=None,
            dedupe_val=bool(request.options.get('dedupe_val')),
            progress_callback=request.progress_callback,
            cancel_check=request.cancel_check,
            project_root=request.project_root,
        )

        exported = None
        if request.export_format:
            exported = self.export(weights, request.export_format, device)
            if request.progress_callback is not None:
                request.progress_callback({
                    'event': 'exported',
                    'path': str(exported),
                    'format': request.export_format,
                })

        return TrainingResult(
            weights=Path(weights),
            run_dir=Path(weights).parent.parent,
            exported=exported,
        )

    def export(self, weights: Path, export_format: str, device: str | int) -> Path:
        """
        Export trained weights with the Ultralytics exporter.

        Args:
            weights (Path): Trained checkpoint
            export_format (str): 'onnx' or 'engine'
            device (str | int): Export device

        Returns:
            Path: The exported artifact
        """
        from system.training import yolo_trainer

        if export_format not in self.export_formats:
            raise ValueError(
                f"Ultralytics provider exports {', '.join(self.export_formats)}; "
                f"'{export_format}' is not supported"
            )
        return yolo_trainer.export_weights(Path(weights), export_format, device)

    def base_models(self) -> list[dict[str, Any]]:
        """Return the Ultralytics checkpoints with their install status."""
        from system.training import yolo_trainer

        return yolo_trainer.get_available_base_models()

    def curated_models(self) -> dict[str, Any]:
        """Return the curated Ultralytics start checkpoints."""
        from system.training import yolo_trainer

        return yolo_trainer.OFFICIAL_BASE_MODELS

    def supports_base_model(self, model_name: str) -> bool:
        """
        Whether Ultralytics can fetch this checkpoint name.

        Args:
            model_name (str): Checkpoint filename

        Returns:
            bool: True for curated names and any other '.pt' weight
        """
        clean_name = Path(model_name).name
        return clean_name in self.curated_models() or clean_name.endswith('.pt')

    def download_base_model(self, model_name: str, progress_callback=None) -> Path:
        """
        Download an official Ultralytics checkpoint.

        Args:
            model_name (str): Checkpoint filename
            progress_callback: Optional callback receiving progress dicts

        Returns:
            Path: The local checkpoint path
        """
        from system.training import yolo_trainer

        return yolo_trainer.download_base_model(model_name, progress_callback=progress_callback)
