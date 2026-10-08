# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 08.10.2026
# Website: https://bespredel.name

"""
Metadata and class extraction utilities for object detection models.
Allows inspecting models (.onnx, .pt, sidecar configs) without strict dependency
on Ultralytics.
"""

import ast
import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def parse_names_dict(raw: Any) -> Dict[int, str]:
    """
    Parse model class names from various representations into {class_id: name}.
    Supports:
        - dict: {0: 'person'} or {'0': 'person'}
        - list: ['person', 'car']
        - string: JSON, Python literal dict, or newline-separated text.
    """
    if raw is None:
        return {}

    if isinstance(raw, dict):
        result = {}
        for k, v in raw.items():
            try:
                result[int(k)] = str(v)
            except (ValueError, TypeError):
                continue
        return result

    if isinstance(raw, (list, tuple)):
        return {i: str(v) for i, v in enumerate(raw)}

    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return {}

        # 1. Try JSON
        try:
            parsed = json.loads(text)
            if isinstance(parsed, (dict, list)):
                return parse_names_dict(parsed)
        except Exception:
            pass

        # 2. Try Python literal eval (e.g. "{0: 'person', 1: 'bicycle'}")
        try:
            parsed = ast.literal_eval(text)
            if isinstance(parsed, (dict, list)):
                return parse_names_dict(parsed)
        except Exception:
            pass

        # 3. Newline or comma separated fallback
        if '\n' in text:
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            return {i: line for i, line in enumerate(lines)}

    return {}


def extract_classes_from_sidecar(weights_path: Path) -> Optional[Tuple[Dict[int, str], str]]:
    """
    Check for sidecar files containing class labels next to model weights:
    - <weights_stem>.json or classes.json
    - <weights_stem>.yaml or data.yaml
    - <weights_stem>.txt or classes.txt
    """
    parent = weights_path.parent
    stem = weights_path.stem

    # 1. JSON
    json_candidates = [weights_path.with_suffix('.json'), parent / f"{stem}_classes.json", parent / "classes.json"]
    for path in json_candidates:
        if path.is_file():
            try:
                with open(path, 'r', encoding='utf-8') as fh:
                    data = json.load(fh)
                    names = data.get('names') if isinstance(data, dict) and 'names' in data else data
                    parsed = parse_names_dict(names)
                    if parsed:
                        return parsed, f"sidecar:{path.name}"
            except Exception:
                pass

    # 2. YAML
    yaml_candidates = [weights_path.with_suffix('.yaml'), parent / "data.yaml", parent / f"{stem}.yaml"]
    for path in yaml_candidates:
        if path.is_file():
            try:
                import yaml
                with open(path, 'r', encoding='utf-8') as fh:
                    data = yaml.safe_load(fh)
                    if isinstance(data, dict):
                        names = data.get('names')
                        parsed = parse_names_dict(names)
                        if parsed:
                            return parsed, f"sidecar:{path.name}"
            except Exception:
                pass

    # 3. TXT (one class per line)
    txt_candidates = [weights_path.with_suffix('.txt'), parent / f"{stem}_classes.txt", parent / "classes.txt"]
    for path in txt_candidates:
        if path.is_file():
            try:
                with open(path, 'r', encoding='utf-8') as fh:
                    lines = [line.strip() for line in fh if line.strip()]
                    if lines:
                        return {i: line for i, line in enumerate(lines)}, f"sidecar:{path.name}"
            except Exception:
                pass

    return None


def extract_classes_from_onnx(weights_path: Path) -> Optional[Tuple[Dict[int, str], str]]:
    """
    Extract class names embedded into ONNX model metadata (custom_metadata_map['names']).
    Works completely without Ultralytics using onnxruntime.
    """
    try:
        import onnxruntime as ort
    except ImportError:
        ort = None

    if ort is not None:
        try:
            # Minimal options for fast metadata read without tensor allocations
            opts = ort.SessionOptions()
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
            opts.intra_op_num_threads = 1
            session = ort.InferenceSession(str(weights_path), sess_options=opts, providers=['CPUExecutionProvider'])
            meta = session.get_modelmeta().custom_metadata_map
            names_raw = meta.get('names')
            parsed = parse_names_dict(names_raw)
            if parsed:
                return parsed, 'onnx_metadata'
        except Exception:
            pass

    # Optional fallback using onnx package if onnxruntime failed to load metadata
    try:
        import onnx
        model = onnx.load(str(weights_path), load_external_data=False)
        for prop in model.metadata_props:
            if prop.key == 'names':
                parsed = parse_names_dict(prop.value)
                if parsed:
                    return parsed, 'onnx_metadata'
    except Exception:
        pass

    return None


def extract_classes_from_pytorch(weights_path: Path) -> Optional[Tuple[Dict[int, str], str]]:
    """
    Extract class names from PyTorch / Ultralytics .pt file if ultralytics is available.
    """
    try:
        from ultralytics import YOLO
        model = YOLO(str(weights_path))
        names = getattr(model, 'names', None)
        parsed = parse_names_dict(names)
        if parsed:
            return parsed, 'ultralytics_weights'
    except Exception:
        pass

    return None


def extract_model_classes(weights: str | Path) -> Tuple[Dict[int, str], Optional[str]]:
    """
    Unified extractor for model class names from any model weights or sidecar files.

    Args:
        weights: Path or string pointing to model weights.

    Returns:
        tuple: (classes_dict: {0: 'person', ...}, source: str | None)
    """
    if not weights:
        return {}, None

    path = Path(weights)
    if not path.is_file():
        return {}, None

    # 1. Check sidecar files first (user overrides)
    sidecar = extract_classes_from_sidecar(path)
    if sidecar:
        return sidecar

    # 2. Check by extension
    ext = path.suffix.lower()
    if ext == '.onnx':
        onnx_res = extract_classes_from_onnx(path)
        if onnx_res:
            return onnx_res
    elif ext in ('.pt', '.pth', '.engine', '.trt'):
        pt_res = extract_classes_from_pytorch(path)
        if pt_res:
            return pt_res

    return {}, None


def get_model_metadata(weights: str | Path) -> Dict[str, Any]:
    """
    Inspect model weights and extract available metadata:
    classes, task, input_shape, stride, etc.
    """
    path = Path(weights) if weights else None
    if not path or not path.is_file():
        return {}

    classes, source = extract_model_classes(path)
    info: Dict[str, Any] = {
        'weights_path': str(path),
        'classes': classes,
        'classes_source': source,
        'format': path.suffix.lower().lstrip('.'),
    }

    if path.suffix.lower() == '.onnx':
        try:
            import onnxruntime as ort
            opts = ort.SessionOptions()
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
            opts.intra_op_num_threads = 1
            session = ort.InferenceSession(str(path), sess_options=opts, providers=['CPUExecutionProvider'])
            meta = session.get_modelmeta().custom_metadata_map
            info['task'] = meta.get('task', 'detect')
            info['stride'] = meta.get('stride')
            inputs = session.get_inputs()
            if inputs:
                shape = inputs[0].shape
                info['input_name'] = inputs[0].name
                info['input_shape'] = shape
                if len(shape) == 4 and isinstance(shape[2], int) and isinstance(shape[3], int):
                    info['input_size'] = [shape[3], shape[2]]
        except Exception:
            pass

    return info
