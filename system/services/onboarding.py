# -*- coding: utf-8 -*-
# ! python3

"""First-run onboarding state stored in configuration."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from system.managers.config_migrator import ONBOARDING_VERSION

VALID_STATES = frozenset({"pending", "completed", "skipped"})
COLLECTION_INTENTS = frozenset({
    "video_test", "collect_dataset", "explore", "collection",
})
TRAIN_INTENT = "train"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


DRAFT_FIELD_KEYS = ("label", "video_path", "weights_path")


def _clean_draft_fields(fields: Optional[Dict[str, Any]]) -> Dict[str, str]:
    source = fields if isinstance(fields, dict) else {}
    return {key: str(source.get(key) or "").strip()[:512] for key in DRAFT_FIELD_KEYS}


def get_onboarding_block(config: Any) -> Dict[str, Any]:
    """Read general.onboarding from a ConfigManager-like object or dict."""
    if config is None:
        return {}
    if hasattr(config, "get"):
        block = config.get("general.onboarding") or {}
    elif isinstance(config, dict):
        general = config.get("general") or {}
        block = general.get("onboarding") or {}
    else:
        block = {}
    return block if isinstance(block, dict) else {}


def get_onboarding_state(config: Any) -> str:
    state = str(get_onboarding_block(config).get("state") or "completed").strip().lower()
    return state if state in VALID_STATES else "completed"


def should_show_welcome(config: Any) -> bool:
    return get_onboarding_state(config) == "pending"


def should_show_resume_hint(config: Any) -> bool:
    return get_onboarding_state(config) == "skipped"


def onboarding_payload(config: Any) -> Dict[str, Any]:
    block = get_onboarding_block(config)
    fields = block.get("fields")
    return {
        "version": block.get("version", ONBOARDING_VERSION),
        "state": get_onboarding_state(config),
        "provenance": block.get("provenance"),
        "scenario": block.get("scenario"),
        "fields": _clean_draft_fields(fields),
        "completed_at": block.get("completed_at"),
        "skipped_at": block.get("skipped_at"),
    }


def set_onboarding_fields(config_manager, fields: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """Remember the values typed in the wizard.

    Installing a component restarts the server, and a reopened wizard would otherwise start
    from empty inputs with no way back to the components step.
    """
    cleaned = _clean_draft_fields(fields)
    block = dict(get_onboarding_block(config_manager))
    block["fields"] = cleaned
    config_manager.set("general.onboarding", block)
    config_manager.save_config()
    return cleaned


def set_onboarding_state(config_manager, *, state: str, provenance: str = "user", scenario: Optional[str] = None) -> None:
    if state not in VALID_STATES:
        raise ValueError(f"Invalid onboarding state: {state}")

    block = dict(get_onboarding_block(config_manager))
    block["version"] = ONBOARDING_VERSION
    block["state"] = state
    block["provenance"] = provenance
    if scenario is not None:
        block["scenario"] = scenario
    now = _utc_now()
    if state == "completed":
        block["completed_at"] = now
    elif state == "skipped":
        block["skipped_at"] = now
    config_manager.set("general.onboarding", block)
    config_manager.save_config()


def intent_requires_inference(intent: Optional[str]) -> bool:
    norm = (intent or "").strip().lower()
    if not norm or norm in COLLECTION_INTENTS:
        return False
    return True


def scenario_to_default_intent(scenario_id: str) -> str:
    mapping = {
        "count_objects": "inference",
        "test_camera": "video_test",
        "collect_dataset": "collect_dataset",
        "own_dataset": "collect_dataset",
        "train": TRAIN_INTENT,
        "custom_weights": "inference",
        "explore": "explore",
    }
    return mapping.get((scenario_id or "").strip().lower(), "explore")
