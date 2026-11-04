# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

"""
Legacy Configuration Compatibility and Migration Layer.

-------------------------------------------------------------------------------
DEPRECATION NOTICE & FUTURE REMOVAL GUIDE:
This module provides a transitional compatibility layer to automatically upgrade
older CVCounter configuration formats to the modern canonical schema.

Legacy configuration items handled by this module:
1. `counting_area`: Single-polygon vertex list [[x, y], ...].
   Migrated into modern multi-zone `counting_areas`: [{'points': [...], 'color': [...], 'direction': '...'}]
2. `counting_area_color`: Global 3-channel BGR color list [B, G, R].
   Migrated into individual zone color `counting_areas[i].color`.
3. `counting_area_direction`: Direction string ('any', 'top_to_bottom', etc.).
   Migrated into individual zone direction `counting_areas[i].direction`.

When all installations are upgraded in future major releases, this compatibility
layer can be cleanly removed by:
  1. Deleting this file (`system/managers/config_migrator.py`).
  2. Removing the single call `migrate_legacy_config(config_data)` in
     `system/managers/config_manager.py`.
-------------------------------------------------------------------------------
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Tuple

from system.utils.logger import Logger

_logger = Logger()

DEFAULT_COUNTING_AREA_COLOR: List[int] = [67, 211, 255]
LEGACY_DETECTION_KEYS: Tuple[str, ...] = (
    "counting_area",
    "counting_area_color",
    "counting_area_direction",
)


def is_legacy_detection_entry(det_cfg: Dict[str, Any]) -> bool:
    """
    Check if a detection dictionary contains any legacy configuration fields.

    Args:
        det_cfg (dict): Detection configuration dictionary.

    Returns:
        bool: True if legacy fields are present.
    """
    if not isinstance(det_cfg, dict):
        return False
    return any(key in det_cfg for key in LEGACY_DETECTION_KEYS)


def is_legacy_config(config_data: Dict[str, Any]) -> bool:
    """
    Check whether a complete application config dictionary contains legacy fields.

    Args:
        config_data (dict): Full configuration dictionary.

    Returns:
        bool: True if any legacy detection or camera setting is detected.
    """
    if not isinstance(config_data, dict):
        return False

    # Check detection_default
    det_default = config_data.get("detection_default")
    if isinstance(det_default, dict) and is_legacy_detection_entry(det_default):
        return True

    # Check detections.<camera>
    detections = config_data.get("detections")
    if isinstance(detections, dict):
        for cam_cfg in detections.values():
            if isinstance(cam_cfg, dict) and is_legacy_detection_entry(cam_cfg):
                return True

    return False


def get_legacy_fields_detected(config_data: Dict[str, Any]) -> List[str]:
    """
    Return a list of paths where legacy configuration fields were detected.

    Args:
        config_data (dict): Full configuration dictionary.

    Returns:
        list[str]: Descriptions of legacy fields found (e.g. "detections.road_cam.counting_area").
    """
    detected: List[str] = []
    if not isinstance(config_data, dict):
        return detected

    det_default = config_data.get("detection_default")
    if isinstance(det_default, dict):
        for key in LEGACY_DETECTION_KEYS:
            if key in det_default:
                detected.append(f"detection_default.{key}")

    detections = config_data.get("detections")
    if isinstance(detections, dict):
        for cam_name, cam_cfg in detections.items():
            if isinstance(cam_cfg, dict):
                for key in LEGACY_DETECTION_KEYS:
                    if key in cam_cfg:
                        detected.append(f"detections.{cam_name}.{key}")

    return detected


def migrate_detection_entry(det_cfg: Dict[str, Any], name: str = "") -> Tuple[Dict[str, Any], bool]:
    """
    Migrate a single detection section (camera config or detection_default).

    Converts legacy single-zone `counting_area`, `counting_area_color`, and
    `counting_area_direction` into modern `counting_areas`. Removes the obsolete
    keys so the stored configuration remains strictly canonical.

    Args:
        det_cfg (dict): Detection configuration dictionary.
        name (str): Identifier for logging (e.g. 'detections.road_cam').

    Returns:
        tuple[dict, bool]: (Updated dictionary, was_modified boolean).
    """
    if not isinstance(det_cfg, dict):
        return det_cfg, False

    migrated = False

    has_legacy_area = "counting_area" in det_cfg
    has_legacy_color = "counting_area_color" in det_cfg
    has_legacy_direction = "counting_area_direction" in det_cfg

    counting_areas = det_cfg.get("counting_areas")
    has_valid_modern_areas = isinstance(counting_areas, list) and len(counting_areas) > 0

    # If modern counting_areas is absent or empty, construct it from legacy fields
    if not has_valid_modern_areas and has_legacy_area:
        legacy_points = det_cfg["counting_area"]
        if isinstance(legacy_points, (list, tuple)) and len(legacy_points) >= 3:
            raw_color = det_cfg.get("counting_area_color")
            color = (
                list(raw_color)
                if isinstance(raw_color, (list, tuple)) and len(raw_color) == 3
                else list(DEFAULT_COUNTING_AREA_COLOR)
            )
            direction = str(det_cfg.get("counting_area_direction") or "any").strip().lower()

            det_cfg["counting_areas"] = [
                {
                    "points": [[int(p[0]), int(p[1])] for p in legacy_points if isinstance(p, (list, tuple)) and len(p) >= 2],
                    "color": [int(color[0]), int(color[1]), int(color[2])],
                    "direction": direction,
                }
            ]
            migrated = True
            _logger.info(f"[LegacyMigrator] Converted single counting_area to counting_areas for '{name or 'camera'}'.")

    # Remove all legacy keys from dictionary
    for legacy_key in LEGACY_DETECTION_KEYS:
        if legacy_key in det_cfg:
            det_cfg.pop(legacy_key, None)
            migrated = True

    return det_cfg, migrated


def migrate_legacy_config(config_data: Dict[str, Any], in_place: bool = True) -> Tuple[Dict[str, Any], bool]:
    """
    Inspect and upgrade all legacy sections across the entire configuration dictionary.

    Args:
        config_data (dict): Application configuration dictionary.
        in_place (bool): If True, modifies the dictionary in-place; otherwise deep-copies.

    Returns:
        tuple[dict, bool]: (Migrated configuration dictionary, was_migrated boolean).
    """
    if not isinstance(config_data, dict):
        return config_data, False

    cfg = config_data if in_place else copy.deepcopy(config_data)
    total_migrated = False

    # 1. Upgrade detection_default
    det_default = cfg.get("detection_default")
    if isinstance(det_default, dict):
        _, migrated = migrate_detection_entry(det_default, name="detection_default")
        if migrated:
            total_migrated = True

    # 2. Upgrade all cameras in detections
    detections = cfg.get("detections")
    if isinstance(detections, dict):
        for cam_name, cam_cfg in detections.items():
            if isinstance(cam_cfg, dict):
                _, migrated = migrate_detection_entry(cam_cfg, name=f"detections.{cam_name}")
                if migrated:
                    total_migrated = True

    if total_migrated:
        _logger.info("[LegacyMigrator] Successfully migrated legacy configuration fields to modern canonical format.")

    return cfg, total_migrated

