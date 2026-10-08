# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 28.07.2026
# Updated: 30.07.2026
# Website: https://bespredel.name


from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Callable, Optional

from system.training.yolo_trainer import (
    DEFAULT_BASE_MODEL,
    DEFAULT_EPOCHS,
    DEFAULT_IMG_SIZE,
    DEFAULT_TASK,
    best_weights_path,
    export_weights,
    list_base_models,
    resolve_device,
    train_model,
)
from system.utils.logger import Logger


class TrainingJobManager:
    """Serialize Ultralytics training jobs and stream progress callbacks."""

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
        """
        Set the progress emitter.
        
        Args:
            emitter (Optional[Callable[[dict], None]]): The progress emitter
        """
        self._progress_emitter = emitter

    def status(self) -> dict[str, Any]:
        """
        Get the status of the training job.
        
        Returns:
            dict[str, Any]: The status of the training job
        """
        with self._lock:
            job = dict(self._job) if self._job else None
            return {
                'busy': bool(self._thread and self._thread.is_alive()),
                'job': job,
                'log': list(self._log_lines[-200:]),
                'history': list(self._history[-20:]),
                'base_models': list_base_models(),
            }

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
        """
        Start a training job.
        
        Args:
            config_name (str): The name of the config
            base_model (str): The base model to use
            epochs (int): The number of epochs to train for
            imgsz (int): The image size to use
            batch (int): The batch size to use
            device (str): The device to use
            task (str): The task to train for
            export_format (str): The export format to use
            dedupe_val (bool): Whether to deduplicate the validation set
            dataset_name (Optional[str]): The name of the dataset
        
        Returns:
            dict[str, Any]: The training job
        """
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
                    weights = train_model(
                        config_name=config_name,
                        base_model=base_model,
                        epochs=epochs,
                        img_size=imgsz,
                        batch=batch,
                        device=resolve_device(device),
                        task=task,
                        export_format=export_format.strip() or None,
                        dedupe_val=dedupe_val,
                        progress_callback=self._on_progress,
                    )
                    with self._lock:
                        if self._job and self._job['id'] == job_id:
                            self._job['status'] = 'completed'
                            self._job['weights'] = str(weights)
                            self._job['finished_at'] = time.time()
                            self._history.append(dict(self._job))
                    self._append_log(f'Training complete: {weights}')
                    self._emit({'event': 'job_complete', 'job': self.status().get('job')})
                except Exception as exc:
                    self.logger.error(f'Training job failed: {exc}')
                    self.logger.log_exception()
                    with self._lock:
                        if self._job and self._job['id'] == job_id:
                            self._job['status'] = 'failed'
                            self._job['error'] = str(exc)
                            self._job['finished_at'] = time.time()
                            self._history.append(dict(self._job))
                    self._append_log(f'Error: {exc}')
                    self._emit({'event': 'job_failed', 'error': str(exc), 'job': self.status().get('job')})

            self._thread = threading.Thread(target=_run, daemon=True, name=f'TrainJob-{job_id}')
            self._thread.start()
            return dict(self._job)

    def cancel(self) -> bool:
        """
        Request cancel. Ultralytics may finish the current epoch before stopping.
        
        Returns:
            bool: Whether the cancel request was successful
        """
        with self._lock:
            if not self._thread or not self._thread.is_alive():
                return False
            self._cancel.set()
            if self._job:
                self._job['status'] = 'cancel_requested'
            self._append_log('Cancel requested (will stop after current step if possible)')
            return True

    def list_runs(self, task: str = DEFAULT_TASK) -> list[dict[str, Any]]:
        """
        List the training runs.
        
        Args:
            task (str): The task to list the runs for
        
        Returns:
            list[dict[str, Any]]: The training runs
        """
        from system.training.yolo_trainer import RUNS_DIR, setup_directories
        setup_directories()
        runs = []
        task_dir = RUNS_DIR / task
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
        """
        Export a training run.
        
        Args:
            config_name (str): The name of the config
            export_format (str): The export format to use
            task (str): The task to export the run for
            device (str): The device to use
        
        Returns:
            str: The path to the exported weights
        """
        weights = best_weights_path(config_name, task)
        if not weights.is_file():
            raise FileNotFoundError(f'Weights not found: {weights}')
        out = export_weights(weights, export_format, resolve_device(device))
        return str(out)

    def _on_progress(self, payload: dict) -> None:
        """
        Handle progress updates.
        
        Args:
            payload (dict): The progress payload
        
        Returns:
            None
        """
        with self._lock:
            if self._job:
                self._job['progress'] = payload
        event = payload.get('event')
        if event == 'epoch_end':
            self._append_log(
                f"Epoch {payload.get('epoch')}/{payload.get('epochs')} {payload.get('metrics')}"
            )
        elif event == 'start':
            self._append_log(f"Train start: {payload}")
        elif event == 'complete':
            self._append_log(f"Weights: {payload.get('weights')}")
        self._emit({'event': 'training_progress', **payload, 'job_id': (self._job or {}).get('id')})

    def _append_log(self, line: str) -> None:
        """
        Append a log line.
        
        Args:
            line (str): The log line to append
        
        Returns:
            None
        """
        with self._lock:
            self._log_lines.append(line)
            if len(self._log_lines) > 1000:
                self._log_lines = self._log_lines[-500:]

    def _emit(self, payload: dict) -> None:
        """
        Emit a payload.
        
        Args:
            payload (dict): The payload to emit
        
        Returns:
            None
        """
        if self._progress_emitter:
            try:
                self._progress_emitter(payload)
            except Exception:
                pass


# Process-wide singleton (wired with socketio emitter from app/routes)
training_job_manager = TrainingJobManager()
