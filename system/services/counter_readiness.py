# -*- coding: utf-8 -*-
# ! python3

"""Counter setup status and readiness checks (composes existing diagnostics)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from system.detection.registry import get_provider_status, resolve_architecture
from system.services.onboarding import intent_requires_inference
from system.utils.paths import resolve_project_path
from system.utils.runtimes import resolve_bundles_for_inference


def counter_uses_collection_mode(cam_cfg: Dict[str, Any], config_path: Optional[str] = None) -> bool:
    """True only when the user did not choose a model.

    A filled weights path means inference was requested, even if the file is not on disk yet.
    """
    del config_path
    if not isinstance(cam_cfg, dict):
        return True
    weights_path = str(cam_cfg.get("weights_path") or "").strip()
    if weights_path:
        return False
    intent = str(cam_cfg.get("inference_intent") or "").strip().lower()
    if intent in ("inference", "train", "count_objects", "custom_weights"):
        return False
    return True


def compute_setup_status(location: str, cam_cfg: Dict[str, Any], config_manager: Any) -> str:
    if str(cam_cfg.get("setup_status") or "").strip().lower() == "template":
        return "template"
    video_path = str(cam_cfg.get("video_path") or "").strip()
    if not video_path:
        return "unconfigured"

    if counter_uses_collection_mode(cam_cfg):
        return "ready"

    weights_path = str(cam_cfg.get("weights_path") or "").strip()
    resolved = resolve_project_path(weights_path) or weights_path
    if weights_path and not os.path.isfile(resolved):
        return "unconfigured"

    plan = resolve_bundles_for_inference(
        inference_intent="inference",
        model_type=cam_cfg.get("model_type"),
        weights_path=weights_path,
    )
    if plan.get("required"):
        return "missing_deps"
    provider = get_provider_status(resolve_architecture(cam_cfg.get("model_type"), weights_path))
    if not provider.get("inference_available"):
        return "missing_deps"
    return "ready"


def build_setup_status_map(config_manager: Any) -> Dict[str, str]:
    detections = config_manager.get("detections") or {}
    if not isinstance(detections, dict):
        return {}
    return {
        loc: compute_setup_status(loc, cfg, config_manager)
        for loc, cfg in detections.items()
        if isinstance(cfg, dict)
    }


def validate_counter_readiness(
    cam_cfg: Dict[str, Any],
    *,
    target_mode: str = "count",
    inference_intent: Optional[str] = None,
) -> Dict[str, Any]:
    """Pre-flight checklist for one counter configuration dict."""
    checks: List[Dict[str, Any]] = []
    mode = (target_mode or "count").strip().lower()
    intent = str(inference_intent or cam_cfg.get("inference_intent") or "").strip()
    video_path = str(cam_cfg.get("video_path") or "").strip()
    weights_path = str(cam_cfg.get("weights_path") or "").strip()
    model_type = str(cam_cfg.get("model_type") or "").strip().lower()
    collection = (
        not weights_path
        and model_type in ("", "auto", "none", "preview")
        and (mode == "collection" or not intent_requires_inference(intent))
    )

    from system.utils.i18n import trans as translate

    if not video_path:
        checks.append({
            "id": "video_source",
            "status": "error",
            "title": translate("Video source"),
            "details": translate("Video source is not configured"),
            "critical": True,
        })
    else:
        checks.append({
            "id": "video_source",
            "status": "ok",
            "title": translate("Video source"),
            "details": video_path,
            "critical": False,
        })

    if collection:
        checks.append({
            "id": "model",
            "status": "info",
            "title": translate("Model"),
            "details": translate("Collection mode — no model required"),
            "critical": False,
        })
        bundles = resolve_bundles_for_inference(
            inference_intent=intent or "collection",
            model_type=cam_cfg.get("model_type"),
            weights_path="",
        )
    else:
        resolved_w = resolve_project_path(weights_path) or weights_path
        if not weights_path or not os.path.isfile(resolved_w):
            checks.append({
                "id": "model",
                "status": "error",
                "title": translate("Model weights"),
                "details": translate("Weights file missing or not configured"),
                "critical": True,
            })
        else:
            checks.append({
                "id": "model",
                "status": "ok",
                "title": translate("Model weights"),
                "details": os.path.basename(weights_path),
                "critical": False,
            })
        bundles = resolve_bundles_for_inference(
            inference_intent="inference",
            model_type=cam_cfg.get("model_type"),
            weights_path=weights_path,
        )
        provider_id = resolve_architecture(cam_cfg.get("model_type"), weights_path)
        provider = get_provider_status(provider_id)
        if not provider.get("inference_available"):
            checks.append({
                "id": "inference_provider",
                "status": "error",
                "title": translate("Inference provider"),
                "details": translate("Provider {name} unavailable", name=provider_id),
                "critical": True,
            })
        else:
            checks.append({
                "id": "inference_provider",
                "status": "ok",
                "title": translate("Inference provider"),
                "details": provider_id,
                "critical": False,
            })

    required_items = bundles.get("items") or []
    blocked_items = bundles.get("blocked") or []
    if required_items:
        names = ", ".join(
            str(item.get("name") or item.get("key") or "")
            for item in required_items
        )
        checks.append({
            "id": "runtime_bundles",
            "status": "warning",
            "title": translate("Runtime components"),
            "details": translate("Install required components: {names}", names=names),
            "critical": True,
        })
    if blocked_items:
        reasons: List[str] = []
        for item in blocked_items:
            item_reasons = [translate(reason) for reason in (item.get("reasons") or [])]
            label = str(item.get("name") or item.get("key") or "")
            reasons.append(f"{label}: {'; '.join(item_reasons) or translate('Not available')}")
        checks.append({
            "id": "runtime_bundles_unavailable",
            "status": "error",
            "title": translate("Runtime components"),
            "details": "; ".join(reasons),
            "critical": True,
        })
    if not required_items and not blocked_items and not collection:
        checks.append({
            "id": "runtime_bundles",
            "status": "ok",
            "title": translate("Runtime components"),
            "details": translate("All required components installed"),
            "critical": False,
        })

    critical_count = sum(1 for c in checks if c.get("critical") and c.get("status") in ("error", "warning"))
    return {
        "checks": checks,
        "critical_count": critical_count,
        "ready": critical_count == 0,
        "bundles": bundles,
        "collection_mode": collection,
    }


def filter_doctor_checks(report: Dict[str, Any], include_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    checks = report.get("checks") or []
    if not include_ids:
        return list(checks)
    allow = set(include_ids)
    return [c for c in checks if c.get("id") in allow]


def build_onboarding_readiness(
    config_manager: Any,
    *,
    scenario: Optional[str] = None,
    location: Optional[str] = None,
    runtime_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    from system.utils.telemetry import get_telemetry

    doctor = get_telemetry().run_system_doctor(runtime_context or {})
    system_checks = filter_doctor_checks(
        doctor,
        include_ids=["storage", "disk_space", "database", "acceleration", "inference_providers"],
    )

    counter_part: Dict[str, Any] = {}
    if location:
        cam_cfg = (config_manager.get("detections") or {}).get(location) or {}
        if isinstance(cam_cfg, dict):
            counter_part = validate_counter_readiness(cam_cfg, target_mode="count")

    bundles = {"required": [], "items": [], "blocked": [], "optional": [], "notes": []}
    if scenario in ("count_objects", "custom_weights", "train"):
        bundles = resolve_bundles_for_inference(
            inference_intent="train" if scenario == "train" else "inference",
            model_type=None,
            weights_path="",
        )

    critical = sum(1 for c in system_checks if c.get("status") == "error")
    critical += counter_part.get("critical_count") or 0
    if bundles.get("required") or bundles.get("blocked"):
        critical += 1

    return {
        "system_checks": system_checks,
        "counter": counter_part,
        "bundles": bundles,
        "critical_count": critical,
        "scenario": scenario,
        "location": location,
    }
