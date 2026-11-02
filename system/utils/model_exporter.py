# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from __future__ import annotations

import shutil
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from system.object_detection.model_spec import load_model_manifest, resolve_model_spec
from system.utils.paths import ensure_dir, get_project_root, resolve_project_path, resolve_training_paths
from system.utils.runtimes import get_export_provider_capabilities


SUPPORTED_EXPORT_FORMATS = ('onnx', 'engine')
SUPPORTED_SOURCE_FORMATS = ('.pt', '.pth', '.onnx', '.engine', '.trt', '.xml', '.bin')
_ULTRALYTICS_TASKS = {'detect', 'object_detection', 'segment', 'pose', 'classify', 'obb'}


@dataclass(frozen=True)
class ExportRequest:
    """Parameters for the existing background export job."""

    weights_path: str
    export_format: str
    half: bool = False
    imgsz: int = 640
    device: str = 'auto'
    dynamic: bool = False
    workspace: int = 4


@dataclass(frozen=True)
class ExportCapabilities:
    """Export support for one target format and a resolved source artifact."""

    format: str
    exporter: str
    supported: bool
    available: bool
    requirements: List[str]
    reasons: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Artifact:
    """Model artifact metadata used by the catalog and legacy export picker."""

    name: str
    path: str
    format: str
    runtime: str
    architecture: Optional[str]
    task: Optional[str]
    preprocessing: Dict[str, Any]
    input_contract: Dict[str, Any]
    output_contract: Dict[str, Any]
    decoder: Optional[str]
    declared_by: str
    size_mb: float
    modified: int
    export_capabilities: Dict[str, Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ModelExportManager:
    """Manages YOLO model conversion to ONNX and TensorRT Engine."""

    _instance: Optional[ModelExportManager] = None
    _lock = threading.Lock()

    def __new__(cls) -> ModelExportManager:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_state()
            return cls._instance

    def _init_state(self) -> None:
        self.state_lock = threading.Lock()
        self.status = 'idle'  # 'idle' | 'running' | 'completed' | 'error'
        self.active_weights: Optional[str] = None
        self.active_format: Optional[str] = None
        self.logs: List[str] = []
        self.error_message: Optional[str] = None
        self.result_path: Optional[str] = None
        self.worker_thread: Optional[threading.Thread] = None

    def get_export_status(self) -> Dict[str, Any]:
        """Return the current status of the model exporter."""
        with self.state_lock:
            return {
                'status': self.status,
                'weights': self.active_weights,
                'format': self.active_format,
                'logs': list(self.logs),
                'result_path': self.result_path,
                'error': self.error_message,
            }

    def list_exportable_models(self) -> List[Dict[str, Any]]:
        """List available .pt models that can be exported."""
        root = Path(get_project_root())
        provider_capabilities = get_export_provider_capabilities()
        runs_dir = resolve_training_paths(root)[2]
        search_dirs = [
            root / 'config' / 'ultralytics' / 'models',
            root / 'config' / 'models',
            runs_dir / 'detect',
            root / 'storage' / 'runs' / 'detect',
        ]
        models: List[Dict[str, Any]] = []
        seen_paths = set()

        for s_dir in search_dirs:
            if not s_dir.is_dir():
                continue
            for pt_file in s_dir.rglob('*.pt'):
                try:
                    rel = str(pt_file.resolve().relative_to(root.resolve())).replace('\\', '/')
                except ValueError:
                    rel = str(pt_file).replace('\\', '/')
                if rel in seen_paths:
                    continue
                seen_paths.add(rel)
                models.append(self._artifact_for_path(pt_file, rel, provider_capabilities))

        models.sort(key=lambda m: m['modified'], reverse=True)
        return models

    def list_model_artifacts(self) -> List[Dict[str, Any]]:
        """Catalog supported model artifacts without implying they are export sources."""
        root = Path(get_project_root())
        runs_dir = resolve_training_paths(root)[2]
        search_dirs = [
            root / 'config' / 'ultralytics' / 'models',
            root / 'config' / 'models',
            runs_dir,
            root / 'storage' / 'runs',
        ]
        artifacts: List[Dict[str, Any]] = []
        seen_paths = set()
        provider_capabilities = get_export_provider_capabilities()
        for search_dir in search_dirs:
            if not search_dir.is_dir():
                continue
            for path in search_dir.rglob('*'):
                if not path.is_file() or path.suffix.lower() not in SUPPORTED_SOURCE_FORMATS:
                    continue
                try:
                    relative_path = str(path.resolve().relative_to(root.resolve())).replace('\\', '/')
                except ValueError:
                    relative_path = str(path).replace('\\', '/')
                if relative_path in seen_paths:
                    continue
                seen_paths.add(relative_path)
                artifacts.append(self._artifact_for_path(path, relative_path, provider_capabilities))
        artifacts.sort(key=lambda item: item['modified'], reverse=True)
        return artifacts

    def _artifact_for_path(
            self,
            path: Path,
            relative_path: str,
            provider_capabilities: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Resolve metadata and source-specific export support for one file."""
        manifest_error = None
        try:
            spec = resolve_model_spec(path)
            manifest = load_model_manifest(path)
        except ValueError as exc:
            manifest_error = str(exc)
            manifest = None
            spec = None

        source_reasons = []
        source_supported = path.suffix.lower() in ('.pt', '.pth')
        if not source_supported:
            source_reasons.append(
                f"Ultralytics exporter accepts .pt/.pth source weights, not '{path.suffix or 'extensionless'}'"
            )
        elif manifest is not None:
            if manifest.architecture != 'yolo':
                source_supported = False
                source_reasons.append(
                    f"Ultralytics exporter does not declare architecture '{manifest.architecture}'"
                )
            if manifest.task not in _ULTRALYTICS_TASKS:
                source_supported = False
                source_reasons.append(
                    f"Ultralytics exporter does not declare task '{manifest.task}'"
                )
            if manifest.format not in ('pt', 'pth'):
                source_supported = False
                source_reasons.append(
                    f"Ultralytics exporter does not accept manifest format '{manifest.format}'"
                )
            if manifest.runtime not in ('yolo', 'ultralytics'):
                source_supported = False
                source_reasons.append(
                    f"Ultralytics exporter does not declare runtime '{manifest.runtime}'"
                )
        elif manifest_error:
            source_supported = False
            source_reasons.append(manifest_error)

        provider_capabilities = provider_capabilities or get_export_provider_capabilities()
        export_capabilities = {}
        for export_format in SUPPORTED_EXPORT_FORMATS:
            provider_capability = provider_capabilities[export_format]
            reasons = list(source_reasons) + list(provider_capability['reasons'])
            export_capabilities[export_format] = ExportCapabilities(
                format=export_format,
                exporter=provider_capability['exporter'],
                supported=source_supported,
                available=source_supported and provider_capability['available'],
                requirements=list(provider_capability['requirements']),
                reasons=reasons,
            ).to_dict()

        try:
            spec_payload = spec.to_dict() if spec else {}
        except Exception:
            spec_payload = {}
        artifact = Artifact(
            name=path.name,
            path=relative_path,
            format=spec_payload.get('format') or path.suffix.lower().lstrip('.'),
            runtime=spec_payload.get('runtime') or 'unknown',
            architecture=spec_payload.get('architecture'),
            task=spec_payload.get('task'),
            preprocessing=spec_payload.get('preprocessing') or {},
            input_contract=spec_payload.get('input_contract') or {},
            output_contract=spec_payload.get('output_contract') or {},
            decoder=spec_payload.get('decoder'),
            declared_by=spec_payload.get(
                'declared_by',
                'invalid_manifest' if manifest_error else 'legacy',
            ),
            size_mb=round(path.stat().st_size / (1024 * 1024), 2),
            modified=int(path.stat().st_mtime),
            export_capabilities=export_capabilities,
        ).to_dict()
        artifact['manifest_error'] = manifest_error
        return artifact

    def get_model_export_capabilities(self, weights_path: str) -> Dict[str, Any]:
        """Return source compatibility and available export formats for one artifact."""
        resolved = self._resolve_weights_path(weights_path)
        if not resolved:
            raise FileNotFoundError(f"Weights file '{weights_path}' not found.")
        return self._artifact_for_path(
            Path(resolved),
            self._relative_artifact_path(Path(resolved)),
        )

    @staticmethod
    def _relative_artifact_path(path: Path) -> str:
        root = Path(get_project_root())
        try:
            return str(path.resolve().relative_to(root.resolve())).replace('\\', '/')
        except ValueError:
            return str(path).replace('\\', '/')

    @staticmethod
    def _resolve_weights_path(weights_path: str) -> Optional[str]:
        resolved_path = resolve_project_path(weights_path)
        if resolved_path and Path(resolved_path).is_file():
            return str(Path(resolved_path).resolve())
        direct = Path(weights_path)
        if direct.is_file():
            return str(direct.resolve())
        return None

    def start_export(
        self,
        weights_path: str,
        export_format: str,
        half: bool = False,
        imgsz: int = 640,
        device: str = 'auto',
        dynamic: bool = False,
        workspace: int = 4,
    ) -> Dict[str, Any]:
        """Validate prerequisites and launch model export in a background thread."""
        fmt = (export_format or '').strip().lower()
        if fmt not in SUPPORTED_EXPORT_FORMATS:
            return {
                'ok': False,
                'error': f"Unsupported export format '{export_format}'. Supported formats: {list(SUPPORTED_EXPORT_FORMATS)}",
            }

        resolved_path = self._resolve_weights_path(weights_path)
        if not resolved_path:
            return {'ok': False, 'error': f"Weights file '{weights_path}' not found."}

        artifact = self._artifact_for_path(
            Path(resolved_path),
            self._relative_artifact_path(Path(resolved_path)),
        )
        capability = artifact['export_capabilities'][fmt]
        if not capability['supported']:
            return {
                'ok': False,
                'error': '; '.join(capability['reasons']) or 'The source model is not supported by this exporter.',
                'error_code': 'unsupported_model',
                'capability': capability,
            }
        if not capability['available']:
            return {
                'ok': False,
                'error': '; '.join(capability['reasons']) or f"Exporter for '{fmt}' is unavailable.",
                'error_code': 'provider_unavailable',
                'capability': capability,
            }

        request = ExportRequest(
            weights_path=weights_path,
            export_format=fmt,
            half=half,
            imgsz=imgsz,
            device=device,
            dynamic=dynamic,
            workspace=workspace,
        )

        with self.state_lock:
            if self.status == 'running':
                return {
                    'ok': False,
                    'error': f"An export job is already running for '{self.active_weights}'.",
                }

            self.status = 'running'
            self.active_weights = weights_path
            self.active_format = fmt
            self.logs = [f"Starting export of {Path(weights_path).name} to {fmt.upper()}..."]
            self.error_message = None
            self.result_path = None

            self.worker_thread = threading.Thread(
                target=self._run_export_worker,
                args=(str(resolved_path), request),
                daemon=True,
            )
            self.worker_thread.start()

        return {'ok': True, 'weights': weights_path, 'format': fmt, 'status': 'running'}

    def _run_export_worker(
        self,
        weights_full_path: str,
        request: ExportRequest,
    ) -> None:
        """Worker thread executing YOLO export."""
        try:
            from ultralytics import YOLO

            fmt = request.export_format
            root = Path(get_project_root())
            models_target_dir = root / 'config' / 'ultralytics' / 'models'
            ensure_dir(str(models_target_dir))

            self._append_log(f"Loading YOLO model from: {weights_full_path}")
            model = YOLO(weights_full_path)

            export_kwargs: Dict[str, Any] = {
                'format': fmt,
                'imgsz': request.imgsz,
                'half': request.half,
                'simplify': True,
            }

            if fmt == 'onnx':
                export_kwargs['dynamic'] = request.dynamic
            elif fmt == 'engine':
                dev = 0 if request.device in ('auto', '0', None, '') else request.device
                export_kwargs['device'] = dev
                export_kwargs['workspace'] = request.workspace

            self._append_log(f"Running model.export with options: {export_kwargs}")
            export_result = model.export(**export_kwargs)

            if not export_result:
                raise RuntimeError(f"Ultralytics export returned empty result for format {fmt}")

            exported_path = Path(export_result)
            self._append_log(f"Export produced file: {exported_path}")

            # If exported file is not inside models_target_dir, copy or keep
            dest_file = models_target_dir / exported_path.name
            if exported_path.resolve() != dest_file.resolve():
                self._append_log(f"Placing exported model into {dest_file}...")
                shutil.copy2(str(exported_path), str(dest_file))
                final_path = dest_file
            else:
                final_path = exported_path

            try:
                rel_result = str(final_path.resolve().relative_to(root.resolve())).replace('\\', '/')
            except ValueError:
                rel_result = str(final_path).replace('\\', '/')

            with self.state_lock:
                self.status = 'completed'
                self.result_path = rel_result
                self.logs.append(f"Model successfully exported: {rel_result}")

        except Exception as exc:
            with self.state_lock:
                self.status = 'error'
                self.error_message = str(exc)
                self.logs.append(f"Export failed: {exc}")

    def _append_log(self, text: str) -> None:
        with self.state_lock:
            self.logs.append(text)
            if len(self.logs) > 500:
                self.logs = self.logs[-500:]


# Global singleton
model_export_manager = ModelExportManager()
