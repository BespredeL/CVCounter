# -*- coding: utf-8 -*-
# ! python3

"""
Unified Training Engine for CVCounter.
Manages multi-architecture model training, fine-tuning, checkpointing, and background execution.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from system.training.base import (
    BaseTrainingProvider,
    TrainingCancelledError,
    TrainingRequest,
    TrainingResult,
)
from system.training.registry import (
    check_training_compatibility,
    load_provider,
    resolve_training_provider,
)

logger = logging.getLogger("cvcounter.training.engine")


class JobState(str, Enum):
    IDLE = "idle"
    PREPARING = "preparing"
    RUNNING = "running"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class JobProgress:
    epoch: int = 0
    total_epochs: int = 0
    batch: int = 0
    total_batches: int = 0
    percent: float = 0.0
    current_loss: float = 0.0
    current_mAP: float = 0.0
    metrics: dict[str, float] = field(default_factory=dict)
    speed_fps: float = 0.0
    eta_seconds: float = 0.0
    message: str = ""


@dataclass
class TrainingJob:
    job_id: str
    architecture: str
    request: TrainingRequest
    state: JobState = JobState.IDLE
    progress: JobProgress = field(default_factory=JobProgress)
    result: Optional[TrainingResult] = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    cancel_event: threading.Event = field(default_factory=threading.Event)
    logs: list[str] = field(default_factory=list)

    @property
    def is_active(self) -> bool:
        return self.state in (JobState.PREPARING, JobState.RUNNING, JobState.VALIDATING)

    def to_dict(self) -> dict[str, Any]:
        return {
            'job_id': self.job_id,
            'architecture': self.architecture,
            'state': self.state.value,
            'progress': asdict(self.progress),
            'started_at': self.started_at,
            'finished_at': self.finished_at,
            'duration_sec': (self.finished_at - self.started_at) if (self.finished_at and self.started_at) else None,
            'error': self.error,
            'weights_path': str(self.result.weights) if self.result and self.result.weights else None,
            'exported_path': str(self.result.exported) if self.result and self.result.exported else None,
            'metrics': self.result.metrics if self.result else self.progress.metrics,
            'recent_logs': self.logs[-20:],
        }


class TrainingEngine:
    """Central engine orchestrating training jobs across detector architectures."""

    def __init__(self, project_root: Optional[Path | str] = None) -> None:
        from system.utils.paths import get_project_root
        self.project_root = Path(project_root or get_project_root())
        self._jobs: dict[str, TrainingJob] = {}
        self._lock = threading.Lock()
        self._active_job_id: Optional[str] = None

    def start_training(
        self,
        architecture: str,
        dataset_name: str,
        dataset_root: str | Path,
        classes: tuple[str, ...],
        epochs: int = 50,
        batch_size: int = 16,
        img_size: int = 640,
        learning_rate: float = 1e-3,
        device: str = "cpu",
        pretrained_weights: Optional[str] = None,
        export_format: Optional[str] = None,
        options: Optional[dict[str, Any]] = None,
    ) -> TrainingJob:
        """Create and dispatch a training job in a background worker thread."""
        with self._lock:
            if self._active_job_id is not None:
                active_job = self._jobs.get(self._active_job_id)
                if active_job and active_job.is_active:
                    raise RuntimeError(
                        f"Another training job '{self._active_job_id}' is already running on architecture '{active_job.architecture}'. "
                        f"Wait for it to finish or cancel it first."
                    )

            import uuid
            job_id = f"train_{int(time.time())}_{uuid.uuid4().hex[:6]}"
            dataset_root_path = Path(dataset_root)

            # Determine dataset format
            ds_fmt = "coco" if architecture in ("rf_detr", "d_fine") else "yolo"

            req_options = dict(options or {})
            req_options.update({
                "lr": learning_rate,
                "learning_rate": learning_rate,
                "pretrained_weights": pretrained_weights,
            })

            cancel_evt = threading.Event()

            request = TrainingRequest(
                config_name=f"{architecture}_{dataset_name}",
                dataset_name=dataset_name,
                dataset_root=dataset_root_path,
                dataset_format=ds_fmt,
                dataset_paths={"root": str(dataset_root_path)},
                classes=classes,
                task="detect",
                base_model=pretrained_weights or f"{architecture}_base",
                epochs=epochs,
                img_size=img_size,
                batch=batch_size,
                device=device,
                provider=architecture,
                export_format=export_format,
                project_root=self.project_root,
                options=req_options,
                cancel_check=lambda: cancel_evt.is_set(),
            )

            job = TrainingJob(
                job_id=job_id,
                architecture=architecture,
                request=request,
                state=JobState.PREPARING,
                cancel_event=cancel_evt,
            )
            self._jobs[job_id] = job
            self._active_job_id = job_id

        # Launch worker thread
        worker = threading.Thread(
            target=self._run_job_worker,
            args=(job,),
            name=f"TrainingWorker-{job_id}",
            daemon=True,
        )
        worker.start()
        return job

    def cancel_job(self, job_id: str) -> bool:
        """Request early cancellation of an active training job."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False
            if not job.is_active:
                return False
            job.cancel_event.set()
            job.logs.append("Cancellation requested by user.")
            return True

    def get_job(self, job_id: str) -> Optional[TrainingJob]:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self) -> list[dict[str, Any]]:
        with self._lock:
            return [job.to_dict() for job in self._jobs.values()]

    def _run_job_worker(self, job: TrainingJob) -> None:
        job.started_at = time.time()
        job.state = JobState.RUNNING

        def on_progress(event: dict[str, Any]) -> None:
            evt_type = event.get("event")
            if evt_type == "epoch_end":
                job.progress.epoch = int(event.get("epoch", job.progress.epoch))
                job.progress.total_epochs = int(event.get("epochs", job.request.epochs))
                if job.progress.total_epochs > 0:
                    job.progress.percent = round((job.progress.epoch / job.progress.total_epochs) * 100.0, 1)
                metrics = event.get("metrics") or {}
                job.progress.metrics = metrics
                job.progress.current_loss = float(metrics.get("loss", metrics.get("train/loss", 0.0)))
                job.progress.current_mAP = float(metrics.get("mAP50", metrics.get("metrics/mAP50(B)", 0.0)))
                job.logs.append(
                    f"Epoch {job.progress.epoch}/{job.progress.total_epochs} - loss: {job.progress.current_loss:.4f}, mAP50: {job.progress.current_mAP:.4f}"
                )
            elif evt_type == "log":
                msg = str(event.get("message", ""))
                job.logs.append(msg)
                job.progress.message = msg

        job.request.progress_callback = on_progress

        try:
            provider = self._resolve_provider(job.architecture)
            provider.prepare(job.request)
            result = provider.train(job.request)

            # Export artifact if requested
            if job.request.export_format and not result.exported:
                try:
                    exp_path = provider.export(result.weights, job.request.export_format, job.request.device)
                    result.exported = exp_path
                except Exception as exp_err:
                    job.logs.append(f"Export warning: {exp_err}")

            job.result = result
            job.state = JobState.COMPLETED
            job.logs.append(f"Training completed successfully. Weights saved to: {result.weights}")

        except TrainingCancelledError:
            job.state = JobState.CANCELLED
            job.logs.append("Training was cancelled.")
        except Exception as exc:
            job.state = JobState.FAILED
            job.error = str(exc)
            job.logs.append(f"Training failed: {exc}")
            logger.exception(f"Job {job.job_id} encountered error: {exc}")
        finally:
            job.finished_at = time.time()
            with self._lock:
                if self._active_job_id == job.job_id:
                    self._active_job_id = None
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass

    def _resolve_provider(self, architecture: str) -> BaseTrainingProvider:
        canon = architecture.strip().lower()
        if canon in ("rf_detr", "rfdetr"):
            from system.training.adapters.rf_detr_trainer import RFDETRTrainingProvider
            return RFDETRTrainingProvider()
        elif canon in ("d_fine", "dfine"):
            from system.training.adapters.d_fine_trainer import DFINETrainingProvider
            return DFINETrainingProvider()
        elif canon in ("rtmdet",):
            from system.training.adapters.rtmdet_trainer import RTMDetTrainingProvider
            return RTMDetTrainingProvider()
        else:
            # Default to ultralytics provider
            return load_provider("ultralytics")
