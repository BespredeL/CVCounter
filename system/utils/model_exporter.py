# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from __future__ import annotations

import os
import shutil
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from system.utils.paths import ensure_dir, get_project_root, resolve_project_path
from system.utils.runtimes import get_gpu_info, is_package_installed


SUPPORTED_EXPORT_FORMATS = ('onnx', 'engine')


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
        search_dirs = [
            root / 'config' / 'ultralytics' / 'models',
            root / 'config' / 'models',
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
                models.append({
                    'name': pt_file.name,
                    'path': rel,
                    'size_mb': round(pt_file.stat().st_size / (1024 * 1024), 2),
                    'modified': int(pt_file.stat().st_mtime),
                })

        models.sort(key=lambda m: m['modified'], reverse=True)
        return models

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

        resolved_path = resolve_project_path(weights_path)
        if not resolved_path or not Path(resolved_path).is_file():
            # Also check direct file path
            direct = Path(weights_path)
            if direct.is_file():
                resolved_path = str(direct.resolve())
            else:
                return {
                    'ok': False,
                    'error': f"Weights file '{weights_path}' not found.",
                }

        # Check dependencies
        if not is_package_installed('ultralytics'):
            return {
                'ok': False,
                'error': "Ultralytics package is required for exporting models. Please install it first.",
            }

        if fmt == 'onnx' and not is_package_installed('onnx'):
            return {
                'ok': False,
                'error': "The 'onnx' package is not installed. Please install the 'ONNX Export & Tools' bundle first.",
            }

        gpu_info = get_gpu_info()
        if fmt == 'engine':
            if not gpu_info['has_nvidia_gpu']:
                return {
                    'ok': False,
                    'error': "Exporting to TensorRT Engine (.engine) requires an NVIDIA GPU with CUDA.",
                }
            if not is_package_installed('tensorrt'):
                return {
                    'ok': False,
                    'error': "The 'tensorrt' package is not installed. Please install the 'TensorRT Acceleration' bundle first.",
                }

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
                args=(str(resolved_path), fmt, half, imgsz, device, dynamic, workspace),
                daemon=True,
            )
            self.worker_thread.start()

        return {'ok': True, 'weights': weights_path, 'format': fmt, 'status': 'running'}

    def _run_export_worker(
        self,
        weights_full_path: str,
        fmt: str,
        half: bool,
        imgsz: int,
        device: str,
        dynamic: bool,
        workspace: int,
    ) -> None:
        """Worker thread executing YOLO export."""
        try:
            from ultralytics import YOLO

            root = Path(get_project_root())
            models_target_dir = root / 'config' / 'ultralytics' / 'models'
            ensure_dir(str(models_target_dir))

            self._append_log(f"Loading YOLO model from: {weights_full_path}")
            model = YOLO(weights_full_path)

            export_kwargs: Dict[str, Any] = {
                'format': fmt,
                'imgsz': imgsz,
                'half': half,
                'simplify': True,
            }

            if fmt == 'onnx':
                export_kwargs['dynamic'] = dynamic
            elif fmt == 'engine':
                dev = 0 if device in ('auto', '0', None, '') else device
                export_kwargs['device'] = dev
                export_kwargs['workspace'] = workspace

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
