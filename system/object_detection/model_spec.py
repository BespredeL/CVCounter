# -*- coding: utf-8 -*-
# ! python3

"""Model contracts and optional sidecar manifest loading."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional


_CONTRACT_FIELDS = (
    'preprocessing',
    'input_contract',
    'output_contract',
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
    def from_dict(cls, data: dict[str, Any]) -> 'ModelManifest':
        if not isinstance(data, dict):
            raise ValueError('Model manifest must be a JSON object')

        schema_version = data.get('schema_version')
        if type(schema_version) is not int or schema_version != 1:
            raise ValueError(f"Unsupported model manifest schema_version: {schema_version!r}")

        required_text = ('architecture', 'task', 'format', 'runtime', 'decoder')
        for field in required_text:
            if not isinstance(data.get(field), str) or not data[field].strip():
                raise ValueError(f"Model manifest field '{field}' must be a non-empty string")

        for field in _CONTRACT_FIELDS:
            if not isinstance(data.get(field), dict):
                raise ValueError(f"Model manifest field '{field}' must be an object")

        return cls(
            architecture=data['architecture'].strip().lower(),
            task=data['task'].strip().lower(),
            format=data['format'].strip().lower(),
            runtime=data['runtime'].strip().lower(),
            preprocessing=data['preprocessing'],
            input_contract=data['input_contract'],
            output_contract=data['output_contract'],
            decoder=data['decoder'].strip().lower(),
            schema_version=schema_version,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ModelSpec:
    """Resolved model metadata without assuming an architecture from its suffix."""

    artifact: str
    architecture: Optional[str]
    task: Optional[str]
    format: str
    runtime: str
    preprocessing: dict[str, Any]
    input_contract: dict[str, Any]
    output_contract: dict[str, Any]
    decoder: Optional[str]
    declared_by: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def manifest_path_for(weights: str | Path) -> Path:
    path = Path(weights)
    return path.with_name(f'{path.stem}.manifest.json')


def load_model_manifest(weights: str | Path) -> Optional[ModelManifest]:
    """Load a versioned sidecar manifest; malformed declarations are explicit errors."""
    manifest_path = manifest_path_for(weights)
    if not manifest_path.is_file():
        return None

    try:
        with manifest_path.open('r', encoding='utf-8') as stream:
            data = json.load(stream)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read model manifest '{manifest_path}': {exc}") from exc

    try:
        return ModelManifest.from_dict(data)
    except ValueError as exc:
        raise ValueError(f"Invalid model manifest '{manifest_path}': {exc}") from exc


def resolve_model_spec(
    weights: str | Path,
    model_type: Optional[str] = None,
) -> ModelSpec:
    """Resolve an explicit manifest or report a conservative legacy model spec."""
    from system.object_detection.registry import resolve_model_type

    path = Path(weights)
    manifest = load_model_manifest(path)
    if manifest is not None:
        return ModelSpec(
            artifact=str(path),
            architecture=manifest.architecture,
            task=manifest.task,
            format=manifest.format,
            runtime=manifest.runtime,
            preprocessing=manifest.preprocessing,
            input_contract=manifest.input_contract,
            output_contract=manifest.output_contract,
            decoder=manifest.decoder,
            declared_by='manifest',
        )

    runtime = resolve_model_type(model_type, str(path))
    return ModelSpec(
        artifact=str(path),
        architecture=None,
        task=None,
        format=path.suffix.lower().lstrip('.'),
        runtime=runtime,
        preprocessing={},
        input_contract={},
        output_contract={},
        decoder=None,
        declared_by='legacy',
    )


def check_provider_compatibility(spec: ModelSpec) -> dict[str, Any]:
    """Check declared provider support without treating runtime loadability as compatibility."""
    from system.object_detection.registry import get_provider_status

    status = get_provider_status(spec.runtime)
    capabilities = status['capabilities']
    reasons = []
    if not spec.architecture or not spec.task or not spec.decoder:
        reasons.append('An explicit manifest is required to verify architecture, task, and decoder')
    else:
        if spec.architecture not in capabilities.get('architectures', []):
            reasons.append(f"Architecture '{spec.architecture}' is not declared by this provider")
        if spec.task not in capabilities.get('tasks', []):
            reasons.append(f"Task '{spec.task}' is not declared by this provider")
        if spec.decoder not in capabilities.get('decoders', []):
            reasons.append(f"Decoder '{spec.decoder}' is not declared by this provider")

    model_format = f'.{spec.format.lstrip(".").lower()}'
    if model_format not in capabilities.get('formats', []):
        reasons.append(f"Format '{model_format}' is not declared by this provider")

    return {
        'provider': status['id'],
        'compatible': not reasons,
        'available': status['available'],
        'reasons': reasons,
    }
