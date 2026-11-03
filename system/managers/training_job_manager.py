# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Optional

from system.training.base import TrainingCancelledError, TrainingRequest
from system.training.registry import (
    DEFAULT_TRAINING_PROVIDER,
    find_run_weights,
    get_provider_definition,
    get_provider_status,
    get_provider_statuses,
    list_runs as registry_list_runs,
    load_provider,
    provider_paths,
    resolve_provider_id,
    resolve_training_provider,
)
from system.utils.logger import Logger
from system.utils.paths import get_project_root

DEFAULT_EPOCHS = 100
DEFAULT_IMG_SIZE = 640
DEFAULT_TASK = 'detect'


class TrainingProviderUnavailableError(RuntimeError):
    """Raised when the requested training provider cannot run on this machine."""


class TrainingJobManager:
    """Manage training jobs independently from any one training framework."""

    def __init__(self, progress_emitter: Optional[Callable[[dict], None]] = None):
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._cancel = threading.Event()
        self._job: Optional[dict[str, Any]] = None
        self._history: list[dict[str, Any]] = []
        self._log_lines: list[str] = []
        self._progress_emitter = progress_emitter
        self.logger = Logger()

    def set_progress_emitter(self, emitter: Optional[Callable[[dict], None]]) -> None:
        """Set the progress emitter."""
        self._progress_emitter = emitter

    @staticmethod
    def provider_status(provider: Optional[str] = None) -> dict[str, Any]:
        """
        Report availability and capabilities of one training provider.

        Args:
            provider (Optional[str]): Provider id or alias; defaults to Ultralytics

        Returns:
            dict[str, Any]: Provider status payload
        """
        return get_provider_status(provider)

    @staticmethod
    def provider_statuses() -> list[dict[str, Any]]:
        """Report availability and capabilities of every training provider."""
        return get_provider_statuses()

    @staticmethod
    def resolve_provider(provider: Optional[str] = None) -> str:
        """
        Resolve a provider id or alias without requiring its dependencies.

        Args:
            provider (Optional[str]): Provider id or alias

        Returns:
            str: The canonical provider id, or the default when unknown
        """
        try:
            return resolve_provider_id(provider or DEFAULT_TRAINING_PROVIDER)
        except ValueError:
            return DEFAULT_TRAINING_PROVIDER

    @staticmethod
    def default_provider(dataset_format: Optional[str] = None, task: str = DEFAULT_TASK) -> str:
        """Resolve the provider that can train this dataset format."""
        return resolve_training_provider('auto', task, dataset_format)

    @staticmethod
    def dataset_format(provider: Optional[str] = None) -> str:
        """Return the dataset format a provider consumes."""
        definition = get_provider_definition(provider or DEFAULT_TRAINING_PROVIDER)
        return definition.dataset_formats[0]

    @classmethod
    def default_base_model(cls, provider: Optional[str] = None) -> str:
        """Return the recommended start checkpoint of a provider."""
        catalog = cls.base_model_catalog(provider)['available']
        for entry in catalog:
            if entry.get('recommended'):
                return entry['name']
        return catalog[0]['name'] if catalog else ''

    @classmethod
    def base_model_catalog(cls, provider: Optional[str] = None) -> dict[str, Any]:
        """
        Return the start checkpoints a provider can use.

        Args:
            provider (Optional[str]): Provider id or alias

        Returns:
            dict[str, Any]: Installed, available and official model entries
        """
        provider_id = cls.ensure_provider_available(provider)
        instance = load_provider(provider_id)
        catalog = instance.base_models()
        return {
            'provider': provider_id,
            'installed': [entry for entry in catalog if entry.get('installed')],
            'available': catalog,
            'official': instance.curated_models(),
        }

    @classmethod
    def ensure_provider_available(cls, provider: Optional[str] = None) -> str:
        """
        Check dependencies and load the provider before a route makes side effects.

        Args:
            provider (Optional[str]): Provider id or alias

        Returns:
            str: The canonical provider id
        """
        provider_id = resolve_provider_id(provider or DEFAULT_TRAINING_PROVIDER)
        status = get_provider_status(provider_id)
        if not status['available']:
            raise TrainingProviderUnavailableError(
                f"Training provider '{provider_id}' is unavailable. {status['error']}. "
                f"Install its dependencies with `python install.py --provider {status['install_provider']}`."
            )
        load_provider(provider_id)
        return provider_id

    def status(self) -> dict[str, Any]:
        """Return the job status payload."""
        with self._lock:
            job = dict(self._job) if self._job else None
            provider = (job or {}).get('provider') or DEFAULT_TRAINING_PROVIDER
            return {
                'busy': bool(self._thread and self._thread.is_alive()),
                'job': job,
                'log': list(self._log_lines[-200:]),
                'history': list(self._history[-20:]),
                'base_models': self.list_base_models(provider),
            }

    @staticmethod
    def list_base_models(provider: Optional[str] = None) -> list[str]:
        """
        List checkpoint files already downloaded for a provider.

        Args:
            provider (Optional[str]): Provider id or alias

        Returns:
            list[str]: Checkpoint filenames
        """
        definition = get_provider_definition(provider or DEFAULT_TRAINING_PROVIDER)
        models_dir = provider_paths(definition.id)[1]
        if not models_dir.is_dir():
            return []
        return sorted(path.name for path in models_dir.glob('*') if path.suffix in ('.pt', '.pth'))

    def build_request(
            self,
            config_name: str,
            *,
            provider: Optional[str] = None,
            base_model: str = '',
            epochs: int = DEFAULT_EPOCHS,
            imgsz: int = DEFAULT_IMG_SIZE,
            batch: int = -1,
            device: str = 'auto',
            task: str = DEFAULT_TASK,
            dataset_format: Optional[str] = None,
            export_format: str = '',
            dedupe_val: bool = False,
            dataset_name: Optional[str] = None,
            dataset_export: Optional[dict[str, Any]] = None,
    ) -> TrainingRequest:
        """
        Validate a job and turn it into a framework-neutral request.

        Args:
            config_name (str): Training run name
            provider (Optional[str]): Provider id or alias
            base_model (str): Start checkpoint; defaults to the provider recommendation
            epochs (int): Number of epochs
            imgsz (int): Training image size
            batch (int): Batch size (-1 = provider default)
            device (str): Device request
            task (str): Training task
            dataset_format (Optional[str]): Dataset format; must be consumed by the provider
            export_format (str): Optional post-training export format
            dedupe_val (bool): Remove validation duplicates from the train split
            dataset_name (Optional[str]): Dataset name; defaults to config_name
            dataset_export (Optional[dict]): Reuse an existing export result

        Returns:
            TrainingRequest: The validated request
        """
        provider_id = self.ensure_provider_available(provider)
        definition = get_provider_definition(provider_id)
        resolved_format = (dataset_format or definition.dataset_formats[0]).strip().lower()
        if resolved_format not in definition.dataset_formats:
            raise ValueError(
                f"Provider '{provider_id}' trains from "
                f"{', '.join(definition.dataset_formats)}, not '{resolved_format}'"
            )
        export = dataset_export or self.export_dataset(dataset_name or config_name, provider_id)

        dataset_paths = self._dataset_paths(export, resolved_format)
        if not dataset_paths:
            raise ValueError(
                f"Dataset export does not contain a '{resolved_format}' artifact; "
                f"export it again for provider '{provider_id}'"
            )

        root = Path(export.get('root') or '')
        request = TrainingRequest(
            config_name=config_name,
            dataset_name=dataset_name or config_name,
            dataset_root=root,
            dataset_format=resolved_format,
            dataset_paths=dataset_paths,
            classes=tuple(export.get('classes') or ()),
            task=task,
            base_model=base_model or self.default_base_model(provider_id),
            epochs=int(epochs),
            img_size=int(imgsz),
            batch=int(batch),
            device=device,
            provider=provider_id,
            export_format=(export_format or '').strip() or None,
            project_root=Path(get_project_root()),
            options={'dedupe_val': bool(dedupe_val)},
        )
        load_provider(provider_id).prepare(request)
        return request

    @staticmethod
    def _dataset_paths(export: dict[str, Any], dataset_format: str) -> dict[str, Any]:
        """
        Extract the artifact paths a provider needs from an export result.

        Args:
            export (dict[str, Any]): Result of DatasetService.export_for_training
            dataset_format (str): 'yolo' or 'coco'

        Returns:
            dict[str, Any]: Provider-facing artifact map
        """
        if dataset_format == 'coco':
            return dict(export.get('coco') or {})
        yaml_path = export.get('yaml')
        return {'yaml': yaml_path} if yaml_path else {}

    @staticmethod
    def export_dataset(dataset_name: str, provider: Optional[str] = None) -> dict[str, Any]:
        """
        Export a dataset in the format the provider consumes.

        Args:
            dataset_name (str): Dataset name
            provider (Optional[str]): Provider id or alias

        Returns:
            dict[str, Any]: Export result
        """
        from system.datasets.dataset_service import DatasetService

        definition = get_provider_definition(provider or DEFAULT_TRAINING_PROVIDER)
        dataset_format = definition.dataset_formats[0]
        return DatasetService(get_project_root()).export_for_training(
            dataset_name, dataset_format=dataset_format
        )

    def start(
            self,
            config_name: str,
            *,
            provider: Optional[str] = None,
            base_model: str = '',
            epochs: int = DEFAULT_EPOCHS,
            imgsz: int = DEFAULT_IMG_SIZE,
            batch: int = -1,
            device: str = 'auto',
            task: str = DEFAULT_TASK,
            dataset_format: Optional[str] = None,
            export_format: str = '',
            dedupe_val: bool = False,
            dataset_name: Optional[str] = None,
            dataset_export: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Validate and launch a training job on the selected provider.

        Args:
            config_name (str): Training run name
            provider (Optional[str]): Provider id or alias
            base_model (str): Start checkpoint; defaults to the provider recommendation
            epochs (int): Number of epochs
            imgsz (int): Training image size
            batch (int): Batch size
            device (str): Device request
            task (str): Training task
            dataset_format (Optional[str]): Dataset format; must be consumed by the provider
            export_format (str): Optional post-training export format
            dedupe_val (bool): Remove validation duplicates from the train split
            dataset_name (Optional[str]): Dataset name
            dataset_export (Optional[dict]): Reuse an existing export result

        Returns:
            dict[str, Any]: The job descriptor
        """
        request = self.build_request(
            config_name,
            provider=provider,
            base_model=base_model,
            epochs=epochs,
            imgsz=imgsz,
            batch=batch,
            device=device,
            task=task,
            dataset_format=dataset_format,
            export_format=export_format,
            dedupe_val=dedupe_val,
            dataset_name=dataset_name,
            dataset_export=dataset_export,
        )
        provider_id = request.provider
        instance = load_provider(provider_id)
        job_request = replace(
            request,
            progress_callback=self._on_progress,
            cancel_check=self._cancel.is_set,
        )

        with self._lock:
            if self._thread and self._thread.is_alive():
                raise RuntimeError('A training job is already running')
            job_id = uuid.uuid4().hex[:12]
            self._cancel.clear()
            self._log_lines = []
            self._job = {
                'id': job_id,
                'provider': provider_id,
                'config': config_name,
                'dataset': request.dataset_name,
                'dataset_format': request.dataset_format,
                'base_model': request.base_model,
                'epochs': request.epochs,
                'imgsz': request.img_size,
                'batch': request.batch,
                'device': request.device,
                'task': request.task,
                'export_format': request.export_format,
                'status': 'running',
                'started_at': time.time(),
                'finished_at': None,
                'weights': None,
                'error': None,
                'progress': {},
            }

            def _run() -> None:
                try:
                    self._append_log(
                        f'Starting training job {job_id} for {config_name} with {provider_id}'
                    )
                    result = instance.train(job_request)
                    with self._lock:
                        if self._job and self._job['id'] == job_id:
                            self._job['status'] = 'completed'
                            self._job['weights'] = str(result.weights)
                            self._job['exported'] = str(result.exported) if result.exported else None
                            self._job['metrics'] = result.metrics
                            self._job['finished_at'] = time.time()
                            self._history.append(dict(self._job))
                    self._append_log(f'Training complete: {result.weights}')
                    self._emit({'event': 'job_complete', 'job': self.status().get('job')})
                except TrainingCancelledError:
                    self.logger.info(f'Training job {job_id} cancelled by user')
                    self._finish_job(job_id, 'cancelled')
                    self._append_log('Training cancelled by user')
                    self._emit({'event': 'job_cancelled', 'job': self.status().get('job')})
                except Exception as exc:
                    if self._cancel.is_set():
                        self.logger.info(f'Training job {job_id} stopped after cancel request: {exc}')
                        self._finish_job(job_id, 'cancelled')
                        self._append_log('Training cancelled by user')
                        self._emit({'event': 'job_cancelled', 'job': self.status().get('job')})
                    else:
                        self.logger.error(f'Training job failed: {exc}')
                        self.logger.log_exception()
                        self._finish_job(job_id, 'failed', str(exc))
                        self._append_log(f'Error: {exc}')
                        self._emit({
                            'event': 'job_failed',
                            'error': str(exc),
                            'job': self.status().get('job'),
                        })

            self._thread = threading.Thread(target=_run, daemon=True, name=f'TrainJob-{job_id}')
            self._thread.start()
            return dict(self._job)

    def _finish_job(self, job_id: str, status: str, error: Optional[str] = None) -> None:
        with self._lock:
            if self._job and self._job['id'] == job_id:
                self._job['status'] = status
                self._job['error'] = error
                self._job['finished_at'] = time.time()
                self._history.append(dict(self._job))

    def cancel(self) -> bool:
        """Request cancellation; the provider may stop at its next safe boundary."""
        with self._lock:
            if not self._thread or not self._thread.is_alive():
                return False
            self._cancel.set()
            if self._job:
                self._job['status'] = 'cancel_requested'
        self._append_log('Cancel requested (will stop after current step if possible)')
        return True

    @staticmethod
    def list_runs(task: str = DEFAULT_TASK, provider: Optional[str] = None) -> list[dict[str, Any]]:
        """
        List finished runs of a provider.

        Args:
            task (str): Task folder inside the runs directory
            provider (Optional[str]): Provider id or alias

        Returns:
            list[dict[str, Any]]: Run descriptors
        """
        return registry_list_runs(provider or DEFAULT_TRAINING_PROVIDER, task)

    @classmethod
    def export_run(
            cls,
            config_name: str,
            export_format: str = 'onnx',
            task: str = DEFAULT_TASK,
            device: str = 'auto',
            provider: Optional[str] = None,
            weights: Optional[Path] = None,
    ) -> str:
        """
        Export a finished run through the provider that trained it.

        Args:
            config_name (str): Training run name
            export_format (str): Target format
            task (str): Task folder inside the runs directory
            device (str): Device request
            provider (Optional[str]): Provider id or alias
            weights (Optional[Path]): Explicit checkpoint; defaults to the run weights

        Returns:
            str: Path of the exported artifact
        """
        provider_id = cls.ensure_provider_available(provider)
        weights_path = Path(weights) if weights else find_run_weights(config_name, task, provider_id)
        if weights_path is None or not Path(weights_path).is_file():
            raise FileNotFoundError(f"Weights not found for run '{config_name}' of provider '{provider_id}'")
        instance = load_provider(provider_id)
        return str(instance.export(Path(weights_path), export_format, instance.resolve_device(device)))

    @classmethod
    def supports_base_model(cls, model_name: str, provider: Optional[str] = None) -> bool:
        """
        Whether a provider can fetch this checkpoint name.

        Args:
            model_name (str): Checkpoint filename
            provider (Optional[str]): Provider id or alias

        Returns:
            bool: True when the provider owns a source for this checkpoint
        """
        provider_id = cls.ensure_provider_available(provider)
        return load_provider(provider_id).supports_base_model(Path(model_name).name)

    def download_base_model(
            self,
            model_name: str,
            progress_callback=None,
            provider: Optional[str] = None,
    ) -> Path:
        """
        Download a start checkpoint through the provider that owns it.

        Args:
            model_name (str): Checkpoint filename
            progress_callback: Optional callback receiving progress dicts
            provider (Optional[str]): Provider id or alias

        Returns:
            Path: The local checkpoint path
        """
        provider_id = self.ensure_provider_available(provider)
        return load_provider(provider_id).download_base_model(model_name, progress_callback=progress_callback)

    def _on_progress(self, payload: dict) -> None:
        """Normalize provider progress into the job and socket contracts."""
        with self._lock:
            if self._job:
                self._job['progress'] = payload
                job_id = self._job.get('id')
            else:
                job_id = None
        event = payload.get('event')
        if event == 'epoch_end':
            self._append_log(
                f"Epoch {payload.get('epoch')}/{payload.get('epochs')} {payload.get('metrics')}"
            )
        elif event == 'start':
            self._append_log(f"Train start: {payload}")
        elif event == 'complete':
            self._append_log(f"Weights: {payload.get('weights')}")
        self._emit({'event': 'training_progress', **payload, 'job_id': job_id})

    def _append_log(self, line: str) -> None:
        with self._lock:
            self._log_lines.append(line)
            if len(self._log_lines) > 1000:
                self._log_lines = self._log_lines[-500:]

    def _emit(self, payload: dict) -> None:
        if self._progress_emitter:
            try:
                self._progress_emitter(payload)
            except Exception:
                pass


# Process-wide singleton (wired with socketio emitter from app/routes)
training_job_manager = TrainingJobManager()
