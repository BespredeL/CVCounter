# -*- coding: utf-8 -*-
# ! python3

"""
Metadata and class extraction utilities for object detection models.
Allows inspecting model weights (.pt, .onnx, sidecar files) and parsing sidecar manifests
without circular dependencies.
"""

from __future__ import annotations

import ast
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

_CONTRACT_FIELDS = (
    "preprocessing",
    "input_contract",
    "output_contract",
)


@dataclass(frozen=True)
class ModelManifest:
    """Portable description of a model independent of its execution runtime."""

    architecture: str
    task: str
    format: str
    runtime: str
    preprocessing: dict[str, Any]
    input_contract: dict[str, Any]
    output_contract: dict[str, Any]
    decoder: str
    schema_version: int = 1

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModelManifest":
        if not isinstance(data, dict):
            raise ValueError("Model manifest must be a JSON object")

        schema_version = data.get("schema_version")
        if type(schema_version) is not int or schema_version != 1:
            raise ValueError(f"Unsupported model manifest schema_version: {schema_version!r}")

        required_text = ("architecture", "task", "format", "runtime", "decoder")
        for field in required_text:
            if not isinstance(data.get(field), str) or not data[field].strip():
                raise ValueError(f"Model manifest field '{field}' must be a non-empty string")

        for field in _CONTRACT_FIELDS:
            if not isinstance(data.get(field), dict):
                raise ValueError(f"Model manifest field '{field}' must be an object")

        return cls(
            architecture=data["architecture"].strip().lower(),
            task=data["task"].strip().lower(),
            format=data["format"].strip().lower(),
            runtime=data["runtime"].strip().lower(),
            preprocessing=data["preprocessing"],
            input_contract=data["input_contract"],
            output_contract=data["output_contract"],
            decoder=data["decoder"].strip().lower(),
            schema_version=schema_version,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def manifest_path_for(weights: Union[str, Path]) -> Path:
    """Return the expected sidecar *.manifest.json path for the given weights."""
    path = Path(weights)
    return path.with_name(f"{path.stem}.manifest.json")


def load_model_manifest(weights: Union[str, Path]) -> Optional[ModelManifest]:
    """Load a versioned sidecar manifest; malformed declarations raise ValueError."""
    manifest_path = manifest_path_for(weights)
    if not manifest_path.is_file():
        return None

    try:
        with manifest_path.open("r", encoding="utf-8") as stream:
            data = json.load(stream)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read model manifest '{manifest_path}': {exc}") from exc

    try:
        return ModelManifest.from_dict(data)
    except ValueError as exc:
        raise ValueError(f"Invalid model manifest '{manifest_path}': {exc}") from exc


def extract_class_name(item: Any) -> str:
    """
    Extract a single class name string from various representations:
    - dict: {'name': 'car', 'enabled': True} -> 'car'
    - stringified dict: "{'name': 'car', 'enabled': True}" -> 'car'
    - plain string or primitive: 'car' -> 'car'
    """
    if isinstance(item, dict):
        for k in ("name", "label", "class_name", "title"):
            if k in item and item[k] is not None:
                return str(item[k]).strip()
        for v in item.values():
            if isinstance(v, str) and v.strip():
                return v.strip()
        return str(item)

    if isinstance(item, str):
        text = item.strip()
        if (text.startswith("{") and text.endswith("}")) or (text.startswith("[") and text.endswith("]")):
            try:
                parsed = json.loads(text)
                return extract_class_name(parsed)
            except Exception:
                try:
                    parsed = ast.literal_eval(text)
                    return extract_class_name(parsed)
                except Exception:
                    pass
        return text

    return str(item).strip() if item is not None else ""


def sanitize_classes_list(raw_list: Any) -> list[str]:
    """
    Normalize any raw classes structure (list of strings, list of dicts,
    stringified JSON/dict, dict of id->name) into a clean list[str].
    Preserves order, eliminates invalid representations, and falls back to
    indexed labels if empty items are encountered.
    """
    if raw_list is None:
        return []

    if isinstance(raw_list, str):
        text = raw_list.strip()
        if not text:
            return []
        if (text.startswith("[") and text.endswith("]")) or (text.startswith("{") and text.endswith("}")):
            try:
                raw_list = json.loads(text)
            except Exception:
                try:
                    raw_list = ast.literal_eval(text)
                except Exception:
                    raw_list = [line.strip() for line in text.splitlines() if line.strip()]
        else:
            raw_list = [line.strip() for line in text.splitlines() if line.strip()]

    items: list[Any] = []
    if isinstance(raw_list, dict):
        try:
            sorted_keys = sorted(raw_list.keys(), key=lambda k: int(k))
        except (ValueError, TypeError):
            sorted_keys = list(raw_list.keys())
        items = [raw_list[k] for k in sorted_keys]
    elif isinstance(raw_list, (list, tuple)):
        items = list(raw_list)
    else:
        items = [raw_list]

    result: list[str] = []
    for i, it in enumerate(items):
        name = extract_class_name(it)
        if not name or name == "None":
            name = f"class_{i}"
        result.append(name)
    return result


def parse_names_dict(raw: Any) -> Dict[int, str]:
    """
    Parse a 'names' structure from various model sources into a Dict[int, str].
    Supports:
    - dict with int or string keys: {0: 'person', 1: 'bicycle'} or {'0': 'person'}
    - list or tuple: ['person', 'bicycle']
    - stringified dict or list (from ONNX metadata properties): "{0: 'person', ...}"
    - YAML-like or JSON string
    """
    if raw is None:
        return {}

    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return {}
        try:
            raw = json.loads(text)
        except Exception:
            try:
                raw = ast.literal_eval(text)
            except Exception:
                try:
                    import yaml

                    raw = yaml.safe_load(text)
                except Exception:
                    return {}

    if isinstance(raw, dict):
        result: Dict[int, str] = {}
        for k, v in raw.items():
            try:
                idx = int(k)
                name = extract_class_name(v)
                if name:
                    result[idx] = name
            except (ValueError, TypeError):
                continue
        return result

    if isinstance(raw, (list, tuple)):
        return {i: extract_class_name(name) for i, name in enumerate(raw) if name is not None}

    return {}


def extract_classes_from_sidecar(weights_path: Path) -> Optional[Tuple[Dict[int, str], str]]:
    """
    Attempt to find class names from sidecar files near the weights file:
    - <stem>.names (one class name per line, Darknet/YOLO convention)
    - <stem>.yaml / <stem>.yml (dataset config containing 'names:')
    - classes.txt in the same directory
    - <stem>.manifest.json (sidecar manifest contract)
    """
    stem = weights_path.stem
    parent = weights_path.parent

    # 1. <stem>.manifest.json
    manifest = load_model_manifest(weights_path)
    if manifest and manifest.output_contract and manifest.output_contract.get("classes"):
        parsed = parse_names_dict(manifest.output_contract["classes"])
        if parsed:
            return parsed, "manifest"

    # 2. <stem>.names
    names_file = parent / f"{stem}.names"
    if names_file.is_file():
        try:
            lines = [line.strip() for line in names_file.read_text(encoding="utf-8").splitlines() if line.strip()]
            if lines:
                return {i: name for i, name in enumerate(lines)}, "sidecar_names"
        except Exception:
            pass

    # 3. <stem>.yaml / <stem>.yml
    for ext in (".yaml", ".yml"):
        yaml_file = parent / f"{stem}{ext}"
        if yaml_file.is_file():
            try:
                import yaml

                with yaml_file.open("r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if isinstance(data, dict) and "names" in data:
                    parsed = parse_names_dict(data["names"])
                    if parsed:
                        return parsed, "sidecar_yaml"
            except Exception:
                pass

    # 4. classes.txt in same directory
    classes_file = parent / "classes.txt"
    if classes_file.is_file():
        try:
            lines = [line.strip() for line in classes_file.read_text(encoding="utf-8").splitlines() if line.strip()]
            if lines:
                return {i: name for i, name in enumerate(lines)}, "sidecar_classes_txt"
        except Exception:
            pass

    return None


def extract_classes_from_onnx(weights_path: Path) -> Optional[Tuple[Dict[int, str], str]]:
    """
    Extract class names embedded in ONNX metadata properties:
    Ultralytics exports embed 'names' as a metadata property inside the ONNX model.
    """
    try:
        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
        opts.intra_op_num_threads = 1
        session = ort.InferenceSession(str(weights_path), sess_options=opts, providers=["CPUExecutionProvider"])
        meta = session.get_modelmeta().custom_metadata_map
        if "names" in meta:
            parsed = parse_names_dict(meta["names"])
            if parsed:
                return parsed, "onnx_metadata"
    except Exception:
        pass

    try:
        import onnx

        model = onnx.load(str(weights_path), load_external_data=False)
        for prop in model.metadata_props:
            if prop.key == "names":
                parsed = parse_names_dict(prop.value)
                if parsed:
                    return parsed, "onnx_metadata"
    except Exception:
        pass

    return None


def extract_classes_from_pytorch(weights_path: Path) -> Optional[Tuple[Dict[int, str], str]]:
    """
    Extract class names from PyTorch checkpoint (.pt):
    Inspects model['model'].names or model['names'] if saved by Ultralytics or TorchVision.
    """
    try:
        import torch

        # Ultralytics checkpoints pickle the model object, so the torch>=2.6 safe unpickler
        # cannot read them; the app already unpickles this same file when loading it for inference.
        checkpoint = torch.load(str(weights_path), map_location="cpu", weights_only=False)
        if isinstance(checkpoint, dict):
            if "model" in checkpoint and hasattr(checkpoint["model"], "names"):
                parsed = parse_names_dict(checkpoint["model"].names)
                if parsed:
                    return parsed, "pytorch_checkpoint"
            if "names" in checkpoint:
                parsed = parse_names_dict(checkpoint["names"])
                if parsed:
                    return parsed, "pytorch_checkpoint"
    except Exception:
        pass

    return None


def _companion_exports(path: Path, suffix: str) -> List[Path]:
    """Same-stem files that can carry class names, in the order they should be read."""
    result: List[Path] = []
    for candidate_suffix in (".onnx", ".pt", ".pth"):
        if candidate_suffix == suffix:
            continue
        candidate = path.with_suffix(candidate_suffix)
        if candidate.is_file():
            result.append(candidate)
    return result


def extract_model_classes(weights: Union[str, Path]) -> Tuple[Dict[int, str], Optional[str]]:
    """
    Unified canonical extractor for model class names from any model weights or sidecar files.

    Args:
        weights: Path or string pointing to model weights file.

    Returns:
        Tuple[Dict[int, str], Optional[str]]: (classes_dict, source).
        Returns ({}, None) if weights file does not exist or classes are not found.
    """
    if not weights:
        return {}, None

    path = Path(weights)
    if not path.is_file():
        return {}, None

    # 1. Check sidecar files first (user overrides, manifest, .names, .yaml)
    sidecar_result = extract_classes_from_sidecar(path)
    if sidecar_result:
        return sidecar_result

    # 2. Extract embedded metadata by file extension
    suffix = path.suffix.lower()
    if suffix == ".onnx":
        onnx_result = extract_classes_from_onnx(path)
        if onnx_result:
            return onnx_result
    elif suffix in (".pt", ".pth", ".bin"):
        torch_result = extract_classes_from_pytorch(path)
        if torch_result:
            return torch_result

    # 3. Formats that store no names (.engine, .torchscript, OpenVINO) normally sit next to the
    #    ONNX or PyTorch export they were built from, and that export does carry them.
    #    ONNX is tried first because reading it cannot run Python code.
    for companion in _companion_exports(path, suffix):
        if companion.suffix.lower() == ".onnx":
            result = extract_classes_from_onnx(companion)
        else:
            result = extract_classes_from_pytorch(companion)
        if result:
            return result

    return {}, None


def get_model_metadata(weights: Union[str, Path]) -> Dict[str, Any]:
    """
    Inspect model weights and extract comprehensive metadata:
    classes, task, input_shape, sidecar manifest contracts.
    """
    path = Path(weights) if weights else None
    if not path or not path.is_file():
        return {}

    classes, source = extract_model_classes(path)
    info: Dict[str, Any] = {
        "weights_path": str(path),
        "classes": classes,
        "classes_source": source,
        "format": path.suffix.lower().lstrip("."),
    }

    manifest = load_model_manifest(path)
    if manifest:
        info["manifest"] = manifest.to_dict()

    if path.suffix.lower() == ".onnx":
        try:
            import onnxruntime as ort

            opts = ort.SessionOptions()
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
            opts.intra_op_num_threads = 1
            session = ort.InferenceSession(str(path), sess_options=opts, providers=["CPUExecutionProvider"])
            meta = session.get_modelmeta().custom_metadata_map
            info["task"] = meta.get("task", "detect")
            info["stride"] = meta.get("stride")
            inputs = session.get_inputs()
            if inputs:
                shape = inputs[0].shape
                info["input_name"] = inputs[0].name
                info["input_shape"] = shape
                if len(shape) == 4 and isinstance(shape[2], int) and isinstance(shape[3], int):
                    info["input_size"] = [shape[3], shape[2]]
        except Exception:
            pass

    return info


__all__ = [
    "ModelManifest",
    "manifest_path_for",
    "load_model_manifest",
    "extract_class_name",
    "sanitize_classes_list",
    "parse_names_dict",
    "extract_classes_from_sidecar",
    "extract_classes_from_onnx",
    "extract_classes_from_pytorch",
    "extract_model_classes",
    "get_model_metadata",
]

