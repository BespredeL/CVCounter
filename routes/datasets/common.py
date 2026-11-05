# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from __future__ import annotations

import os
import time
from pathlib import Path

from flask import jsonify

from system.datasets.dataset_service import DatasetService
from system.detection.metadata import extract_class_name, sanitize_classes_list
from system.managers.training_job_manager import training_job_manager
from system.utils.app_context import get_app_context
from system.utils.logger import Logger
from system.utils.paths import (
    get_project_root,
    resolve_project_path,
    resolve_training_paths,
)

logger = Logger()

try:
    import cv2
    _cv2_import_error: Exception | None = None
except ImportError as exc:
    cv2 = None
    _cv2_import_error = exc

_service_instance: DatasetService | None = None
_cached_project_root: str | None = None


def _service() -> DatasetService:
    """
    Get or create the cached dataset service instance.
    
    Returns:
        DatasetService: The dataset service instance
    """
    global _service_instance, _cached_project_root
    root = get_project_root()
    if _service_instance is None or _cached_project_root != root:
        _cached_project_root = root
        _service_instance = DatasetService(root)
    return _service_instance


def _json_error(message: str, status: int = 400):
    """
    Return a JSON error response.
    
    Args:
        message: The error message
        status: The HTTP status code

    Returns:
        tuple: (JSON response, status code)
    """
    return jsonify({'status': 'error', 'message': message}), status


def _get_detections_config(context: dict | None = None) -> dict:
    """Safely extract detections dict from app context configuration."""
    if context is None:
        context = get_app_context()
    cfg = context.get('config') if context else None
    if isinstance(cfg, dict):
        return cfg.get('detections') or {}
    if hasattr(cfg, 'get'):
        return cfg.get('detections') or {}
    return {}


_cached_detector_models: list[dict] | None = None
_cached_detector_models_time: float = 0.0
_DETECTOR_MODELS_CACHE_TTL: float = 15.0
_MODEL_EXTENSIONS = {'.onnx', '.pt', '.engine', '.trt'}


def invalidate_detector_models_cache() -> None:
    """Invalidate detector models memory cache."""
    global _cached_detector_models, _cached_detector_models_time
    _cached_detector_models = None
    _cached_detector_models_time = 0.0


def _list_detector_models(force_refresh: bool = False) -> list[dict]:
    """
    Detectors and standalone model files for auto-label model picker.
    Uses single-pass directory scanning and TTL memory caching.
    
    Returns:
        list: List of detector and model items
    """
    global _cached_detector_models, _cached_detector_models_time
    now = time.time()
    if not force_refresh and _cached_detector_models is not None and (now - _cached_detector_models_time) < _DETECTOR_MODELS_CACHE_TTL:
        return _cached_detector_models

    context = get_app_context()
    items = []
    seen_paths = set()

    detections = _get_detections_config(context)
    for location, cfg in detections.items():
        weights = (cfg or {}).get('weights_path')
        if not weights:
            continue
        resolved = resolve_project_path(weights)
        exists = bool(resolved and Path(resolved).is_file())
        if resolved:
            seen_paths.add(str(Path(resolved).resolve()))
        items.append({
            'location': location,
            'weights_path': weights,
            'label': f"{location}: {Path(weights).name}",
            'exists': exists,
        })

    try:
        models_dir = resolve_training_paths(get_project_root())[1]
        for mdir in [models_dir, Path(get_project_root()) / 'config' / 'models']:
            if not mdir or not mdir.is_dir():
                continue
            for p in sorted(mdir.iterdir()):
                if not p.is_file() or p.suffix.lower() not in _MODEL_EXTENSIONS:
                    continue
                abs_p = str(p.resolve())
                if abs_p in seen_paths:
                    continue
                seen_paths.add(abs_p)
                items.append({
                    'location': f'model:{p.name}',
                    'weights_path': str(p),
                    'label': f'File: {p.name}',
                    'exists': True,
                })
    except Exception as exc:
        logger.debug(f"Error listing detector models: {exc}")

    _cached_detector_models = items
    _cached_detector_models_time = now
    return items


_cached_weights_for_deploy: list[dict] | None = None
_cached_weights_time: float = 0.0
_WEIGHTS_CACHE_TTL: float = 15.0
_DEPLOY_EXTENSIONS = {'.pt', '.pth', '.onnx', '.engine'}


def invalidate_available_weights_cache() -> None:
    """Invalidate available deployment weights memory cache."""
    global _cached_weights_for_deploy, _cached_weights_time
    _cached_weights_for_deploy = None
    _cached_weights_time = 0.0


def _scan_weights_in_dir(sdir: Path, seen_paths: set[str], root: Path, trained_items: list[dict]) -> None:
    """Helper for single-pass scanning of trained weights in a directory tree."""
    if not sdir.is_dir():
        return
    for root_path, _, filenames in os.walk(sdir):
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in _DEPLOY_EXTENSIONS:
                continue
            p = Path(root_path) / fname
            abs_p = str(p.resolve())
            if abs_p in seen_paths:
                continue
            seen_paths.add(abs_p)

            try:
                rel = p.relative_to(root).as_posix()
            except ValueError:
                rel = str(p).replace('\\', '/')

            try:
                stat = p.stat()
                mtime = stat.st_mtime
                size_mb = round(stat.st_size / (1024 * 1024), 1)
                date_str = time.strftime('%d.%m.%Y %H:%M', time.localtime(mtime))
            except OSError:
                mtime = 0
                size_mb = 0
                date_str = ''

            run_name = p.parent.parent.name if p.parent.name == 'weights' else p.parent.name
            label = f"{run_name} / {p.name} ({size_mb} MB, {date_str})" if date_str else f"{run_name} / {p.name}"

            trained_items.append({
                'path': rel,
                'name': p.name,
                'run_name': run_name,
                'label': label,
                'category': 'trained_runs',
                'mtime': mtime,
                'is_best': p.name in ('best.pt', 'best.pth'),
            })


def _list_available_weights_for_deploy(force_refresh: bool = False) -> list[dict]:
    """
    List trained runs (best.pt, last.pt, exports) and current counter detector weights
    for selection in the deploy step.
    Optimized with single-pass traversal and TTL caching.
    """
    global _cached_weights_for_deploy, _cached_weights_time
    now = time.time()
    if not force_refresh and _cached_weights_for_deploy is not None and (now - _cached_weights_time) < _WEIGHTS_CACHE_TTL:
        return _cached_weights_for_deploy

    root = Path(get_project_root()).resolve()
    seen_paths: set[str] = set()
    trained_items: list[dict] = []

    try:
        _, _, runs_dir, _ = resolve_training_paths(root)
        search_dirs = [runs_dir, root / 'storage' / 'runs']
        config_dir = root / 'config'
        if config_dir.is_dir():
            for p_dir in config_dir.iterdir():
                if p_dir.is_dir() and p_dir.name.startswith('runs'):
                    search_dirs.append(p_dir)

        for sdir in search_dirs:
            _scan_weights_in_dir(sdir, seen_paths, root, trained_items)
    except Exception as exc:
        logger.debug(f"Error scanning trained runs: {exc}")

    trained_items.sort(key=lambda x: (not x['is_best'], -x['mtime']))

    context = get_app_context()
    detector_items: list[dict] = []
    try:
        detections = _get_detections_config(context)
        for location, cfg in detections.items():
            weights = (cfg or {}).get('weights_path')
            if not weights:
                continue
            resolved = resolve_project_path(weights)
            try:
                rel_det_path = Path(resolved).resolve().relative_to(root).as_posix() if resolved else str(weights).replace('\\', '/')
            except (ValueError, RuntimeError, OSError):
                rel_det_path = str(weights).replace('\\', '/')
            detector_items.append({
                'path': rel_det_path,
                'name': Path(str(weights)).name,
                'run_name': location,
                'label': f"{location}: {Path(str(weights)).name}",
                'category': 'active_detectors',
                'mtime': 0,
                'is_best': False,
            })
    except Exception as exc:
        logger.debug(f"Error listing detector weights: {exc}")

    result = trained_items + detector_items
    _cached_weights_for_deploy = result
    _cached_weights_time = now
    return result


def _ordered_class_names(classes_map) -> list[str]:
    """
    Normalize dict/list class maps to an ordered name list (names only, dense).
    
    Args:
        classes_map: The class map
    
    Returns:
        list: Ordered list of class names
    """
    if not classes_map:
        return []
    if isinstance(classes_map, list):
        return sanitize_classes_list(classes_map)
    if isinstance(classes_map, dict):
        items: list[tuple[int, str]] = []
        for key, value in classes_map.items():
            try:
                idx = int(key)
            except (TypeError, ValueError):
                continue
            name = extract_class_name(value)
            if name:
                items.append((idx, name))
        items.sort(key=lambda pair: pair[0])
        return [name for _, name in items]
    return []


def _class_id_map(classes_map) -> dict[int, str]:
    """
    Build sparse YOLO class-id -> name map from config-style dict/list.
    
    Args:
        classes_map: The class map
    
    Returns:
        dict: Sparse YOLO class-id -> name map
    """
    if not classes_map:
        return {}
    if isinstance(classes_map, list):
        cleaned = sanitize_classes_list(classes_map)
        return {i: name for i, name in enumerate(cleaned)}
    if isinstance(classes_map, dict):
        mapping: dict[int, str] = {}
        for key, value in classes_map.items():
            try:
                idx = int(key)
            except (TypeError, ValueError):
                continue
            name = extract_class_name(value)
            if name:
                mapping[idx] = name
        return mapping
    return {}


def _resolve_detector_cfg(detector: str | None = None) -> tuple[dict, str | None]:
    """
    Return (detector config dict, location key). Empty detector -> first with weights.
    
    Args:
        detector: The detector key
    
    Returns:
        tuple: (detector config dict, location key)
    """
    context = get_app_context()
    detections = _get_detections_config(context)

    location = (detector or '').strip()
    if location.startswith('model:'):
        model_name = location[6:]
        models_dir = resolve_training_paths(get_project_root())[1]
        for mdir in [models_dir, Path(get_project_root()) / 'config' / 'models']:
            cand = mdir / model_name
            if cand.is_file():
                return {'weights_path': str(cand), 'model_type': 'auto'}, location

    if location and location in detections:
        return detections[location] or {}, location

    for loc, item in detections.items():
        if (item or {}).get('weights_path'):
            return item or {}, loc
    return {}, None


_model_classes_cache: dict[str, tuple[dict, str | None]] = {}


def _detector_class_names(detector: str | None = None) -> tuple[list[str], str | None, str | None]:
    """
    Resolve class names for a detector: config `classes` first, then YOLO `names`.
    Caches parsed classes by weights file path and mtime.

    Args:
        detector: Detection location key. Empty/None uses the first detector with weights.

    Returns:
        tuple: (class names, source `config`|`weights`, resolved detector location)
    """
    cfg, location = _resolve_detector_cfg(detector)
    if not cfg:
        return [], None, None

    from_config = _ordered_class_names(cfg.get('classes'))
    if from_config:
        return from_config, 'config', location

    weights = cfg.get('weights_path')
    path = resolve_project_path(weights) if weights else None
    if not path or not Path(path).is_file():
        return [], None, location

    try:
        p = Path(path)
        mtime = p.stat().st_mtime
        cache_key = f"{p.resolve()}:{mtime}"
        if cache_key in _model_classes_cache:
            classes_dict, source = _model_classes_cache[cache_key]
        else:
            from system.detection.metadata import extract_model_classes
            classes_dict, source = extract_model_classes(path)
            _model_classes_cache[cache_key] = (classes_dict, source)

        if classes_dict:
            return _ordered_class_names(classes_dict), source or 'weights', location
        return [], None, location
    except Exception as exc:
        logger.debug(f"Error extracting detector class names: {exc}")
        return [], None, location


def _autolabel_label_for_cls(
        cls_id: int,
        *,
        dataset_classes: list[str],
        detector_map: dict[int, str],
        model_names: dict,
        dataset_classes_lower: dict[str, str] | None = None,
) -> str | None:
    """
    Map a YOLO class id to a dataset label name.

    Uses the detector's sparse id->name map (or model.names). Never indexes a densified
    name list with a sparse YOLO id.
    
    Args:
        cls_id: The class id
        dataset_classes: The dataset classes
        detector_map: The detector map
        model_names: The model names
        dataset_classes_lower: Optional precomputed lowercased mapping to avoid allocation
    
    Returns:
        str | None: The label name
    """
    raw = detector_map.get(cls_id)
    if raw is None and model_names:
        raw = model_names.get(cls_id)
        if raw is None:
            raw = model_names.get(str(cls_id))
    if raw is None and not detector_map and dataset_classes and 0 <= cls_id < len(dataset_classes):
        raw = dataset_classes[cls_id]
    if raw is None:
        return None

    name = str(raw).strip()
    if not name:
        return None
    if not dataset_classes:
        return name
    if name in dataset_classes:
        return name
    if dataset_classes_lower is None:
        dataset_classes_lower = {c.lower(): c for c in dataset_classes if isinstance(c, str)}
    return dataset_classes_lower.get(name.lower())


def _resolve_autolabel_weights(
        meta: dict,
        explicit_weights: str | None = None,
        detector: str | None = None,
) -> Path | None:
    """
    Resolve model weights for autolabel/active learning.
    
    Args:
        meta: Dataset metadata dict
        explicit_weights: Optional explicit weights path
        detector: Optional detector location
    
    Returns:
        Path | None: Resolved weights Path
    """
    if explicit_weights:
        path = resolve_project_path(explicit_weights)
        if path and Path(path).is_file():
            return Path(path)

    context = get_app_context()
    detections = _get_detections_config(context)
    location = (detector or meta.get('autolabel_detector') or '').strip()
    if location.startswith('model:'):
        model_name = location[6:]
        models_dir = resolve_training_paths(get_project_root())[1]
        for mdir in [models_dir, Path(get_project_root()) / 'config' / 'models']:
            cand = mdir / model_name
            if cand.is_file():
                return cand

    if location and location in detections:
        weights = (detections[location] or {}).get('weights_path')
        if weights:
            path = resolve_project_path(weights)
            return Path(path) if path else None

    for cfg in detections.values():
        weights = (cfg or {}).get('weights_path')
        if weights:
            path = resolve_project_path(weights)
            if path:
                return Path(path)
    return None


_emitter_wired = False


def _wire_training_emitter() -> None:
    """
    Wire the training progress emitter once.
    """
    global _emitter_wired
    if _emitter_wired:
        return

    context = get_app_context()
    socketio = context.get('socketio') if context else None
    if not socketio:
        return

    def _emit(payload: dict) -> None:
        ctx = get_app_context()
        sio = ctx.get('socketio') if ctx else None
        if sio:
            sio.emit('training_progress', payload)
        if isinstance(payload, dict) and payload.get('stage') in ('completed', 'finished', 'exported'):
            invalidate_available_weights_cache()
            invalidate_detector_models_cache()

    training_job_manager.set_progress_emitter(_emit)
    _emitter_wired = True
