# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from __future__ import annotations

import importlib
import importlib.util
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

from system.utils.logger import Logger
from system.utils.paths import get_project_root, resolve_training_paths

DEFAULT_BASE_MODEL = 'yolo11n.pt'
DEFAULT_EPOCHS = 100
DEFAULT_IMG_SIZE = 640
DEFAULT_TASK = 'detect'


class TrainingProviderUnavailableError(RuntimeError):
    """Raised when the requested built-in training provider is unavailable."""


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
    def provider_status() -> dict[str, Any]:
        """Report availability of the built-in Ultralytics training provider."""
        dependencies: dict[str, bool] = {}
        missing = []
        for dependency in ('torch', 'ultralytics'):
            try:
                available = importlib.util.find_spec(dependency) is not None
            except (ImportError, ModuleNotFoundError, ValueError):
                available = False
            dependencies[dependency] = available
            if not available:
                missing.append(dependency)

        return {
            'id': 'ultralytics',
            'available': not missing,
            'status': 'available' if not missing else 'unavailable',
            'dependencies': dependencies,
            'error': f"Missing dependencies: {', '.join(missing)}" if missing else None,
        }

    @classmethod
    def _load_yolo_provider(cls):
        status = cls.provider_status()
        if not status['available']:
            raise TrainingProviderUnavailableError(
                f"YOLO training is unavailable. {status['error']}. "
                "Install the optional Ultralytics training dependencies to enable it."
            )
        try:
            return importlib.import_module('system.training.yolo_trainer')
        except Exception as exc:
            raise TrainingProviderUnavailableError(
                f"YOLO training provider failed to load: {exc}"
            ) from exc

    @classmethod
    def ensure_provider_available(cls) -> None:
        """Check dependencies and load the provider before a route makes side effects."""
        cls._load_yolo_provider()

    @staticmethod
    def _load_yolo_catalog():
        try:
            return importlib.import_module('system.training.yolo_trainer')
        except Exception as exc:
            raise TrainingProviderUnavailableError(
                f"YOLO model catalog is unavailable: {exc}"
            ) from exc

    def base_model_catalog(self) -> dict[str, Any]:
        """Return the existing Ultralytics model picker data without requiring training."""
        provider = self._load_yolo_catalog()
        return {
            'installed': provider.list_base_models(),
            'available': provider.get_available_base_models(),
            'official': provider.OFFICIAL_BASE_MODELS,
        }

    def status(self) -> dict[str, Any]:
        """Return the legacy job status payload."""
        with self._lock:
            job = dict(self._job) if self._job else None
            return {
                'busy': bool(self._thread and self._thread.is_alive()),
                'job': job,
                'log': list(self._log_lines[-200:]),
                'history': list(self._history[-20:]),
                'base_models': self.list_base_models(),
            }

    @staticmethod
    def list_base_models() -> list[str]:
        """List local `.pt` files without loading the training framework."""
        models_dir = resolve_training_paths(get_project_root())[1]
        if not models_dir.is_dir():
            return []
        return sorted(path.name for path in models_dir.glob('*.pt'))

    def start(
            self,
            config_name: str,
            *,
            base_model: str = DEFAULT_BASE_MODEL,
            epochs: int = DEFAULT_EPOCHS,
            imgsz: int = DEFAULT_IMG_SIZE,
            batch: int = -1,
            device: str = 'auto',
            task: str = DEFAULT_TASK,
            export_format: str = '',
            dedupe_val: bool = False,
            dataset_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Validate and launch a training job using the built-in YOLO provider."""
        provider = self._load_yolo_provider()
        with self._lock:
            if self._thread and self._thread.is_alive():
                raise RuntimeError('A training job is already running')
            job_id = uuid.uuid4().hex[:12]
            self._cancel.clear()
            self._log_lines = []
            self._job = {
                'id': job_id,
                'config': config_name,
                'dataset': dataset_name or config_name,
                'base_model': base_model,
                'epochs': epochs,
                'imgsz': imgsz,
                'batch': batch,
                'device': device,
                'task': task,
                'export_format': export_format or None,
                'status': 'running',
                'started_at': time.time(),
                'finished_at': None,
                'weights': None,
                'error': None,
                'progress': {},
            }

            def _run() -> None:
                try:
                    self._append_log(f'Starting training job {job_id} for {config_name}')
                    weights = provider.train_model(
                        config_name=config_name,
                        base_model=base_model,
                        epochs=epochs,
                        img_size=imgsz,
                        batch=batch,
                        device=provider.resolve_device(device),
                        task=task,
                        export_format=export_format.strip() or None,
                        dedupe_val=dedupe_val,
                        progress_callback=self._on_progress,
                        cancel_check=self._cancel.is_set,
                    )
                    with self._lock:
                        if self._job and self._job['id'] == job_id:
                            self._job['status'] = 'completed'
                            self._job['weights'] = str(weights)
                            self._job['finished_at'] = time.time()
                            self._history.append(dict(self._job))
                    self._append_log(f'Training complete: {weights}')
                    self._emit({'event': 'job_complete', 'job': self.status().get('job')})
                except provider.TrainingCancelledError:
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

    def list_runs(self, task: str = DEFAULT_TASK) -> list[dict[str, Any]]:
        """List best.pt artifacts from the existing Ultralytics run layout."""
        _, _, runs_dir, _ = resolve_training_paths(get_project_root())
        runs = []
        task_dir = runs_dir / task
        if not task_dir.is_dir():
            return runs
        for path in sorted(task_dir.iterdir(), reverse=True):
            weights = path / 'weights' / 'best.pt'
            if weights.is_file():
                runs.append({
                    'name': path.name,
                    'task': task,
                    'weights': str(weights),
                    'mtime': weights.stat().st_mtime,
                })
        return runs

    def export_run(self, config_name: str, export_format: str = 'onnx', task: str = DEFAULT_TASK,
                   device: str = 'auto') -> str:
        """Export a best.pt artifact through the Ultralytics training provider."""
        provider = self._load_yolo_provider()
        weights = provider.best_weights_path(config_name, task)
        if not weights.is_file():
            raise FileNotFoundError(f'Weights not found: {weights}')
        out = provider.export_weights(weights, export_format, provider.resolve_device(device))
        return str(out)

    def download_base_model(self, model_name: str, progress_callback=None) -> Path:
        """Download a supported base model using the Ultralytics provider."""
        provider = self._load_yolo_provider()
        return provider.download_base_model(model_name, progress_callback=progress_callback)

    def _on_progress(self, payload: dict) -> None:
        """Normalize provider progress into the existing job and socket contracts."""
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
