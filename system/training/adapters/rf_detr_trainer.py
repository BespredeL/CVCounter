# -*- coding: utf-8 -*-
# ! python3

"""
RF-DETR Training Provider for CVCounter.
Provides fine-tuning and training for Roboflow RF-DETR models.
"""

from __future__ import annotations

import json
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Optional, Union

from system.training.base import (
    BaseTrainingProvider,
    TrainingCancelledError,
    TrainingRequest,
    TrainingResult,
)


DEFAULT_BASE_MODEL = "rf-detr-nano.pth"

BASE_MODELS: dict[str, dict[str, Any]] = {
    "rf-detr-nano.pth": {
        "name": "RF-DETR Nano (COCO)",
        "task": "detect",
        "size_mb": 349.3,
        "speed": "Very Fast",
        "recommended": True,
        "description": "Compact Roboflow RF-DETR Nano Real-Time Detection Transformer.",
        "url": "https://storage.googleapis.com/rfdetr/nano_coco/checkpoint_best_regular.pth",
        "code_license": "Apache-2.0",
        "code_license_url": "https://github.com/roboflow/rf-detr/blob/main/LICENSE",
        "weights_license": "Apache-2.0 / Dataset-dependent",
        "weights_license_url": None,
        "dataset_license": "Mixed / Flickr Terms (images) & CC-BY-4.0 (annotations)",
        "dataset_license_url": "https://cocodataset.org/#termsofuse",
        "license_status": "unverified",
        "weights_license_status": "unverified",
        "license_url": "https://github.com/roboflow/rf-detr/blob/main/LICENSE",
        "source_url": "https://github.com/roboflow/rf-detr",
    },
    "rf-detr-small.pth": {
        "name": "RF-DETR Small (COCO)",
        "task": "detect",
        "size_mb": 368.1,
        "speed": "Fast",
        "recommended": False,
        "description": "Fast Roboflow RF-DETR Small for real-time inference on modern GPUs.",
        "url": "https://storage.googleapis.com/rfdetr/small_coco/checkpoint_best_regular.pth",
        "code_license": "Apache-2.0",
        "code_license_url": "https://github.com/roboflow/rf-detr/blob/main/LICENSE",
        "weights_license": "Apache-2.0 / Dataset-dependent",
        "weights_license_url": None,
        "dataset_license": "Mixed / Flickr Terms (images) & CC-BY-4.0 (annotations)",
        "dataset_license_url": "https://cocodataset.org/#termsofuse",
        "license_status": "unverified",
        "weights_license_status": "unverified",
        "license_url": "https://github.com/roboflow/rf-detr/blob/main/LICENSE",
        "source_url": "https://github.com/roboflow/rf-detr",
    },
    "rf-detr-medium.pth": {
        "name": "RF-DETR Medium (COCO)",
        "task": "detect",
        "size_mb": 386.2,
        "speed": "Medium",
        "recommended": False,
        "description": "Balanced Roboflow RF-DETR Medium detection model.",
        "url": "https://storage.googleapis.com/rfdetr/medium_coco/checkpoint_best_regular.pth",
        "code_license": "Apache-2.0",
        "code_license_url": "https://github.com/roboflow/rf-detr/blob/main/LICENSE",
        "weights_license": "Apache-2.0 / Dataset-dependent",
        "weights_license_url": None,
        "dataset_license": "Mixed / Flickr Terms (images) & CC-BY-4.0 (annotations)",
        "dataset_license_url": "https://cocodataset.org/#termsofuse",
        "license_status": "unverified",
        "weights_license_status": "unverified",
        "license_url": "https://github.com/roboflow/rf-detr/blob/main/LICENSE",
        "source_url": "https://github.com/roboflow/rf-detr",
    },
    "rf-detr-base.pth": {
        "name": "RF-DETR Base (COCO)",
        "task": "detect",
        "size_mb": 355.3,
        "speed": "Medium",
        "recommended": False,
        "description": "Standard Roboflow RF-DETR Base checkpoint.",
        "url": "https://storage.googleapis.com/rfdetr/rf-detr-base-coco.pth",
        "code_license": "Apache-2.0",
        "code_license_url": "https://github.com/roboflow/rf-detr/blob/main/LICENSE",
        "weights_license": "Apache-2.0 / Dataset-dependent",
        "weights_license_url": None,
        "dataset_license": "Mixed / Flickr Terms (images) & CC-BY-4.0 (annotations)",
        "dataset_license_url": "https://cocodataset.org/#termsofuse",
        "license_status": "unverified",
        "weights_license_status": "unverified",
        "license_url": "https://github.com/roboflow/rf-detr/blob/main/LICENSE",
        "source_url": "https://github.com/roboflow/rf-detr",
    },
}


@dataclass
class CheckpointValidationResult:
    """Structured result of checkpoint validation across distinct tiers."""
    file_valid: bool = False
    structurally_valid: bool = False
    model_compatible: Optional[bool] = None  # None if model_cls was not provided; True/False if checked
    stage: str = "init"  # "file_check", "load_torch", "structure_check", "compatibility_check", "passed"
    error: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        """
        Checkpoint is valid strictly when:
        1. file_valid is True.
        2. structurally_valid is True.
        3. model_compatible is NOT False (if model_cls was provided, it must be True).
        """
        if not (self.file_valid and self.structurally_valid):
            return False
        if self.model_compatible is not None and not self.model_compatible:
            return False
        return True


def validate_rfdetr_checkpoint(
    cand: Path,
    model_cls=None,
    return_detail: bool = False,
    allow_unsafe_legacy_weights: bool = False,
) -> Union[bool, CheckpointValidationResult]:
    """
    Validate candidate checkpoint across three distinct tiers without silent fallback:
    - Tier 1 (file_valid): File exists and size > 0 bytes.
    - Tier 2 (structurally_valid): Valid PyTorch mapping containing genuine torch.Tensor parameters.
    - Tier 3 (model_compatible): Compatibility with the target model_cls.

    Args:
        cand: Checkpoint file path.
        model_cls: Optional model class callable for compatibility verification.
        return_detail: If True, returns CheckpointValidationResult; if False, returns bool.
        allow_unsafe_legacy_weights: If True, explicitly allows weights_only=False deserialization
                                     for verified legacy checkpoints. Defaults to False.

    Returns:
        bool or CheckpointValidationResult
    """
    cand = Path(cand)
    # Tier 1: File integrity check
    if not cand.is_file() or cand.stat().st_size == 0:
        res = CheckpointValidationResult(
            file_valid=False,
            structurally_valid=False,
            model_compatible=None,
            stage="file_check",
            error=f"Checkpoint file does not exist or is empty: {cand}",
        )
        return res if return_detail else res.is_valid

    # Tier 2: Deserialization and state dict structure check
    try:
        import torch

        if allow_unsafe_legacy_weights:
            ckpt = torch.load(cand, map_location="cpu", weights_only=False)
        else:
            ckpt = torch.load(cand, map_location="cpu", weights_only=True)
    except Exception as exc:
        res = CheckpointValidationResult(
            file_valid=True,
            structurally_valid=False,
            model_compatible=None,
            stage="load_torch",
            error=f"PyTorch safe deserialization (weights_only=True) failed: {exc}" if not allow_unsafe_legacy_weights else f"PyTorch failed to deserialize checkpoint: {exc}",
        )
        return res if return_detail else res.is_valid

    if not isinstance(ckpt, dict):
        res = CheckpointValidationResult(
            file_valid=True,
            structurally_valid=False,
            model_compatible=None,
            stage="structure_check",
            error=f"Checkpoint root must be a dict mapping, got {type(ckpt).__name__}",
        )
        return res if return_detail else res.is_valid

    state_dict = None
    if "model" in ckpt and isinstance(ckpt["model"], dict):
        state_dict = ckpt["model"]
    elif "state_dict" in ckpt and isinstance(ckpt["state_dict"], dict):
        state_dict = ckpt["state_dict"]
    elif any(
        isinstance(k, str)
        and any(w in k.lower() for w in ("weight", "bias", "backbone", "transformer", "encoder", "decoder", "embed", "proj"))
        for k in ckpt.keys()
    ):
        state_dict = ckpt

    if not state_dict or len(state_dict) == 0:
        res = CheckpointValidationResult(
            file_valid=True,
            structurally_valid=False,
            model_compatible=None,
            stage="structure_check",
            error="Checkpoint contains empty state dict or no weight mappings",
        )
        return res if return_detail else res.is_valid

    # Validate that state dict values are genuine torch tensors/parameters, not arbitrary primitives
    tensor_count = 0
    non_tensor_types = []
    for k, v in state_dict.items():
        if isinstance(v, (torch.Tensor, torch.nn.Parameter)):
            tensor_count += 1
        else:
            non_tensor_types.append((k, type(v).__name__))

    if tensor_count == 0 or non_tensor_types:
        res = CheckpointValidationResult(
            file_valid=True,
            structurally_valid=False,
            model_compatible=None,
            stage="structure_check",
            error=f"State dict values are not valid torch tensors. Found non-tensor entries: {non_tensor_types[:3]}",
        )
        return res if return_detail else res.is_valid

    # Tier 3: Verify instantiation and weight compatibility if model_cls is provided
    if model_cls is not None:
        try:
            _ = model_cls(pretrain_weights=str(cand))
            res = CheckpointValidationResult(
                file_valid=True,
                structurally_valid=True,
                model_compatible=True,
                stage="passed",
            )
            return res if return_detail else res.is_valid
        except Exception as comp_err:
            res = CheckpointValidationResult(
                file_valid=True,
                structurally_valid=True,
                model_compatible=False,
                stage="compatibility_check",
                error=f"Checkpoint incompatible with model class '{getattr(model_cls, '__name__', str(model_cls))}': {comp_err}",
            )
            return res if return_detail else res.is_valid

    res = CheckpointValidationResult(
        file_valid=True,
        structurally_valid=True,
        model_compatible=None,
        stage="passed",
    )
    return res if return_detail else res.is_valid


class RFDETRTrainingProvider(BaseTrainingProvider):
    id: str = "rf_detr"
    tasks: tuple[str, ...] = ("detect",)
    dataset_formats: tuple[str, ...] = ("coco", "yolo")
    export_formats: tuple[str, ...] = ()
    BASE_MODELS = BASE_MODELS

    def train(self, request: TrainingRequest) -> TrainingResult:
        if request.cancel_check and request.cancel_check():
            raise TrainingCancelledError("Training was cancelled before start.")

        try:
            import rfdetr
        except ImportError:
            raise RuntimeError(
                "RF-DETR training is unavailable: missing 'rfdetr' package. "
                "Install it using: pip install -r requirements-rfdetr.txt"
            )

        run_dir = request.run_dir or (self.runs_dir(request.project_root) / request.task / request.run_name)
        run_dir.mkdir(parents=True, exist_ok=True)
        weights_dir = run_dir / "weights"
        weights_dir.mkdir(parents=True, exist_ok=True)

        variant = str(request.options.get("variant", "small")).lower()
        model_cls_map = {
            "nano": getattr(rfdetr, "RFDETRNano", None),
            "small": getattr(rfdetr, "RFDETRSmall", None),
            "medium": getattr(rfdetr, "RFDETRMedium", None),
            "large": getattr(rfdetr, "RFDETRLarge", None),
            "base": getattr(rfdetr, "RFDETRBase", None),
        }
        model_cls = model_cls_map.get(variant)
        if model_cls is None:
            model_cls = (
                getattr(rfdetr, "RFDETRSmall", None)
                or getattr(rfdetr, "RFDETRNano", None)
                or getattr(rfdetr, "RFDETRMedium", None)
                or getattr(rfdetr, "RFDETR", None)
            )

        if model_cls is None:
            raise RuntimeError(f"RF-DETR variant '{variant}' is not available in the installed rfdetr package.")

        base_model = request.options.get("pretrained_weights") or request.base_model
        model_path = None
        if base_model:
            cand = Path(base_model)
            if not cand.is_file():
                cand = self.models_dir() / base_model
            if not cand.is_file() and self.supports_base_model(base_model):
                try:
                    cand = self.download_base_model(base_model, progress_callback=request.progress_callback)
                except Exception as dl_err:
                    raise RuntimeError(
                        f"Failed to load or download pretrained weights '{base_model}' for RF-DETR: {dl_err}"
                    ) from dl_err
            if cand.is_file():
                model_path = cand
            else:
                raise FileNotFoundError(
                    f"Pretrained weights file not found: '{base_model}' for RF-DETR"
                )

        if model_path:
            model = model_cls(pretrain_weights=str(model_path))
        else:
            model = model_cls()

        batch_size = request.batch if request.batch and request.batch > 0 else 4
        device_str = str(request.device)

        if request.progress_callback:
            request.progress_callback({
                "status": "training",
                "message": f"Starting RF-DETR ({variant}) training on {device_str}...",
            })

        train_kwargs: dict[str, Any] = {
            "dataset_dir": str(request.dataset_root),
            "epochs": request.epochs,
            "batch_size": batch_size,
            "lr": float(request.options.get("lr", 1e-4)),
            "output_dir": str(run_dir),
            "device": device_str,
        }

        # Note on RF-DETR cancellation:
        # The high-level rfdetr.RFDETR*.train() interface does not support arbitrary callback
        # routing in its public signature. Safe cancellation is verified at execution boundaries:
        # prior to start and immediately upon train exit. In-flight loop interruption requires
        # lower-level PyTorch Lightning trainer decoupling (tracked in EXT/TRAIN-RFDETR-INFLIGHT-CANCEL).
        train_result = model.train(**train_kwargs)

        if request.cancel_check and request.cancel_check():
            raise TrainingCancelledError("Training was cancelled by user.")

        # Checkpoint validation without fallback
        candidate_checkpoints = [
            weights_dir / "best.pth",
            run_dir / "checkpoint_best_total.pth",
            run_dir / "checkpoint_best_regular.pth",
            run_dir / "checkpoint_best_ema.pth",
            run_dir / "checkpoint.pth",
            run_dir / "best.pth",
            run_dir / "last.pth",
        ]
        if run_dir.is_dir():
            for p in run_dir.rglob("*.pth"):
                if p not in candidate_checkpoints:
                    candidate_checkpoints.append(p)
            for p in run_dir.rglob("*.pt"):
                if p not in candidate_checkpoints:
                    candidate_checkpoints.append(p)

        final_weights = None
        validation_diagnostics = []
        for cand in candidate_checkpoints:
            v_res = validate_rfdetr_checkpoint(cand, model_cls=model_cls, return_detail=True)
            if v_res.is_valid:
                final_weights = cand
                break
            else:
                validation_diagnostics.append(f"{cand.name}: [{v_res.stage}] {v_res.error}")

        # CRITICAL: NO FALLBACK to model_cls=None!
        # If model_cls was checked and failed, the checkpoint is strictly rejected.
        if final_weights is None or not final_weights.is_file():
            diag_str = "; ".join(validation_diagnostics) if validation_diagnostics else "no candidate checkpoints found"
            raise RuntimeError(
                f"RF-DETR training finished but no valid compatible checkpoint was found in '{run_dir}'. Details: {diag_str}"
            )

        # Normalize final weights location so standard weights/best.pth is always present
        best_standard = weights_dir / "best.pth"
        if final_weights.resolve() != best_standard.resolve():
            try:
                import shutil
                shutil.copy2(final_weights, best_standard)
                final_weights = best_standard
            except Exception as copy_err:
                raise RuntimeError(
                    f"Failed to copy RF-DETR checkpoint from '{final_weights}' to standard location '{best_standard}': {copy_err}"
                ) from copy_err

        # Extract only real metrics; do NOT return hardcoded dummy metrics
        metrics: dict[str, Any] = {}
        if isinstance(train_result, dict):
            for k in ("mAP50", "mAP_50", "map_50", "loss", "final_loss", "mAP50-95"):
                if k in train_result and isinstance(train_result[k], (int, float)):
                    metrics[k] = train_result[k]
            if "metrics" in train_result and isinstance(train_result["metrics"], dict):
                for k, v in train_result["metrics"].items():
                    if isinstance(v, (int, float)):
                        metrics[k] = v

        res_file = run_dir / "results.json"
        if res_file.is_file():
            try:
                with open(res_file, "r", encoding="utf-8") as f:
                    res_data = json.load(f)
                    if isinstance(res_data, dict):
                        for k, v in res_data.items():
                            if isinstance(v, (int, float)):
                                metrics[k] = v
            except Exception:
                pass

        return TrainingResult(
            weights=final_weights,
            run_dir=run_dir,
            metrics=metrics,
        )

    def export(self, weights: Path, export_format: str, device: str | int) -> Path:
        raise NotImplementedError(
            f"Provider '{self.id}' does not implement '{export_format}' export. "
            "RF-DETR models should be exported using official RF-DETR export utilities."
        )
