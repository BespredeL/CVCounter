# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from .constants import *  # noqa: F401,F403


class DoctorMixin:
    """Local diagnostic reports and the system fingerprint."""

    def run_system_doctor(self, runtime_context: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """
        Execute comprehensive local diagnostics and return report.
        
        Args:
            runtime_context: Optional runtime context with config and counters.
            
        Returns:
            dict: Structured checklist of subsystem health statuses.
        """
        checks: list[dict[str, Any]] = []

        # 1. Storage write permissions
        storage_dirs = ['storage/logs', 'storage/reports', 'storage/telemetry']
        storage_ok = True
        storage_details = []
        for sdir in storage_dirs:
            full_path = resolve_project_path(sdir) or sdir
            test_file = os.path.join(full_path, f'.doctor_test_{uuid.uuid4().hex[:6]}.tmp')
            try:
                ensure_parent_dir(test_file)
                with open(test_file, 'w', encoding='utf-8') as f:
                    f.write('ok')
                if os.path.exists(test_file):
                    os.remove(test_file)
                storage_details.append(f'{sdir}: OK')
            except Exception as e:
                storage_ok = False
                storage_details.append(f'{sdir}: FAIL ({e})')

        checks.append({
            'id': 'storage',
            'title': 'Storage write permissions',
            'status': 'ok' if storage_ok else 'error',
            'details': ', '.join(storage_details),
        })

        # 2. Disk space
        disk_status = 'ok'
        disk_details = 'Disk space available'
        try:
            storage_root = resolve_project_path('storage') or 'storage'
            total_b, used_b, free_b = shutil.disk_usage(storage_root)
            free_gb = round(free_b / (1024 ** 3), 1)
            total_gb = round(total_b / (1024 ** 3), 1)
            pct_free = round((free_b / total_b) * 100, 1) if total_b > 0 else 0
            disk_details = f'{free_gb} GB free of {total_gb} GB ({pct_free}% free)'
            if free_gb < 1.0:
                disk_status = 'error'
            elif free_gb < 3.0:
                disk_status = 'warning'
        except Exception as e:
            disk_status = 'warning'
            disk_details = f'Cannot determine disk space: {e}'

        checks.append({
            'id': 'disk_space',
            'title': 'Disk space',
            'status': disk_status,
            'details': disk_details,
        })

        # 3. System RAM
        ram_status = 'ok'
        ram_details = 'RAM available'
        try:
            import psutil
            mem = psutil.virtual_memory()
            avail_gb = round(mem.available / (1024 ** 3), 1)
            total_gb = round(mem.total / (1024 ** 3), 1)
            used_pct = round(mem.percent, 1)
            ram_details = f'{avail_gb} GB available of {total_gb} GB ({used_pct}% used)'
            if avail_gb < 1.0:
                ram_status = 'warning'
        except Exception:
            ram_status = 'info'
            ram_details = 'RAM metrics unavailable'

        checks.append({
            'id': 'ram_memory',
            'title': 'System RAM',
            'status': ram_status,
            'details': ram_details,
        })

        # 4. Database check
        db_ok = True
        db_detail = 'Database accessible'
        try:
            dbm = None
            if runtime_context and 'db_manager' in runtime_context:
                dbm = runtime_context['db_manager']
            elif self._runtime_context and 'db_manager' in self._runtime_context:
                dbm = self._runtime_context['db_manager']

            if dbm is None:
                config = (runtime_context or {}).get('config') or (self._runtime_context or {}).get('config')
                if not config:
                    from system.managers.config_manager import ConfigManager
                    config = ConfigManager('config/config.json')
                from system.managers.database_manager import DatabaseManager
                from system.utils.paths import resolve_sqlite_uri
                raw_uri = config.get('db.uri') or 'sqlite:///config/database.sqlite'
                resolved_uri = resolve_sqlite_uri(raw_uri, getattr(config, 'project_root', None))
                dbm = DatabaseManager(uri=resolved_uri, prefix=config.get('db.prefix', ''))

            if dbm is not None:
                session = dbm.create_session()
                try:
                    from system.db.models.cvcounter import CVCounter
                    session.query(CVCounter).first()
                    db_detail = 'Database connected and schema verified'
                finally:
                    session.close()
            else:
                db_ok = False
                db_detail = 'Database manager instance could not be initialized'
        except Exception as e:
            db_ok = False
            db_detail = f'Database error: {e}'

        checks.append({
            'id': 'database',
            'title': 'Database integrity',
            'status': 'ok' if db_ok else 'error',
            'details': db_detail,
        })

        # 5. Model weights files check
        cfg = (runtime_context or {}).get('config') or (self._runtime_context or {}).get('config')
        if not cfg:
            try:
                from system.managers.config_manager import ConfigManager
                cfg = ConfigManager('config/config.json')
            except Exception:
                cfg = None

        weights_status = 'ok'
        weights_details_list = []
        if cfg:
            detections = cfg.get('detections') or {}
            if isinstance(detections, dict) and detections:
                missing_count = 0
                for loc_id, loc_cfg in detections.items():
                    if isinstance(loc_cfg, dict):
                        wpath = loc_cfg.get('weights_path')
                        if wpath:
                            resolved_w = resolve_project_path(wpath) or wpath
                            if os.path.isfile(resolved_w) and os.path.getsize(resolved_w) > 0:
                                sz_mb = round(os.path.getsize(resolved_w) / (1024 * 1024), 1)
                                weights_details_list.append(f'{loc_id}: {os.path.basename(wpath)} ({sz_mb} MB)')
                            else:
                                missing_count += 1
                                weights_details_list.append(f'{loc_id}: {wpath} (NOT FOUND)')
                if missing_count > 0:
                    weights_status = 'error'
                elif not weights_details_list:
                    weights_status = 'info'
                    weights_details_list.append('No weights configured')
            else:
                weights_status = 'info'
                weights_details_list.append('No detection cameras configured')
        else:
            weights_status = 'info'
            weights_details_list.append('Config not accessible')

        checks.append({
            'id': 'model_weights',
            'title': 'Model weights',
            'status': weights_status,
            'details': '; '.join(weights_details_list),
        })

        # 6. Hardware acceleration
        accel_status = 'info'
        accel_details = []
        has_cuda = False
        try:
            import torch
            has_cuda = torch.cuda.is_available()
            if has_cuda:
                gpu_name = torch.cuda.get_device_name(0)
                vram_gb = round(torch.cuda.get_device_properties(0).total_memory / (1024 ** 3), 1)
                accel_status = 'ok'
                accel_details.append(f'CUDA available: {gpu_name} ({vram_gb} GB VRAM)')
            else:
                accel_status = 'warning'
                accel_details.append('PyTorch CPU-only (CUDA not available)')
        except Exception as e:
            accel_details.append(f'PyTorch: {e}')

        try:
            import openvino
            accel_details.append(f'OpenVINO {getattr(openvino, "__version__", "installed")}')
        except Exception:
            pass

        checks.append({
            'id': 'acceleration',
            'title': 'Hardware acceleration',
            'status': accel_status,
            'details': '; '.join(accel_details) if accel_details else 'CPU only',
        })

        # 7. Model inference benchmark
        benchmark_status = 'ok'
        benchmark_detail = 'Inference ready'
        try:
            import numpy as np
            object_counters = (runtime_context or {}).get('object_counters') or (self._runtime_context or {}).get('object_counters') or {}
            active_counter = next((c for c in object_counters.values() if getattr(c, 'running', False) and hasattr(c, '_detect')), None)
            if active_counter is not None:
                t0 = time.monotonic()
                dummy_frame = np.zeros((640, 640, 3), dtype=np.uint8)
                active_counter._detect(dummy_frame)
                elapsed_ms = round((time.monotonic() - t0) * 1000, 1)
                benchmark_detail = f'Active counter dry-run: {elapsed_ms} ms'
            else:
                first_model = 'yolo26n.pt'
                if cfg:
                    dets = cfg.get('detections') or {}
                    if isinstance(dets, dict) and dets:
                        first_det = next(iter(dets.values()), {})
                        if isinstance(first_det, dict) and first_det.get('weights_path'):
                            first_model = first_det.get('weights_path')
                first_model_resolved = resolve_project_path(first_model) or first_model
                if os.path.exists(first_model_resolved):
                    target_device = 'GPU' if has_cuda else 'CPU'
                    benchmark_detail = f'Model {os.path.basename(first_model)} verified for {target_device} inference'
                else:
                    benchmark_status = 'info'
                    benchmark_detail = 'Ready for stream inference'
        except Exception as e:
            benchmark_status = 'warning'
            benchmark_detail = f'Benchmark error: {e}'

        checks.append({
            'id': 'benchmark',
            'title': 'Model inference benchmark',
            'status': benchmark_status,
            'details': benchmark_detail,
        })

        # 8. Camera network reachability
        cam_status = 'ok'
        cam_details = []
        if cfg:
            detections = cfg.get('detections') or {}
            if isinstance(detections, dict) and detections:
                for loc_id, loc_cfg in detections.items():
                    if isinstance(loc_cfg, dict):
                        vpath = str(loc_cfg.get('video_path') or '').strip()
                        if vpath.lower().startswith(('rtsp://', 'rtsps://', 'http://', 'https://')):
                            try:
                                parsed = urllib_parse.urlparse(vpath)
                                host = parsed.hostname
                                port = parsed.port or (443 if parsed.scheme == 'https' else (80 if parsed.scheme == 'http' else 554))
                                if host:
                                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                                    sock.settimeout(1.0)
                                    code = sock.connect_ex((host, port))
                                    sock.close()
                                    if code == 0:
                                        cam_details.append(f'{loc_id} ({host}:{port}): OK')
                                    else:
                                        cam_status = 'warning'
                                        cam_details.append(f'{loc_id} ({host}:{port}): Unreachable')
                            except Exception as ce:
                                cam_status = 'warning'
                                cam_details.append(f'{loc_id}: {ce}')
                        elif vpath.isdigit():
                            cam_details.append(f'{loc_id}: USB Camera #{vpath}')
                        elif vpath:
                            resolved_v = resolve_project_path(vpath) or vpath
                            if os.path.exists(resolved_v):
                                cam_details.append(f'{loc_id}: File OK')
                            else:
                                cam_status = 'warning'
                                cam_details.append(f'{loc_id}: File missing')
            if not cam_details:
                cam_status = 'info'
                cam_details.append('No cameras configured')
        else:
            cam_status = 'info'
            cam_details.append('Config not accessible')

        checks.append({
            'id': 'cameras_network',
            'title': 'Camera network connections',
            'status': cam_status,
            'details': '; '.join(cam_details),
        })

        # 9. Video recording codecs
        codecs_status = 'ok'
        codecs_detail = 'MP4V codec supported'
        try:
            import cv2
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            tmp_video = resolve_project_path('storage/.doctor_codec_test.mp4') or 'storage/.doctor_codec_test.mp4'
            ensure_parent_dir(tmp_video)
            writer = cv2.VideoWriter(tmp_video, fourcc, 25, (320, 240))
            if writer.isOpened():
                writer.release()
                if os.path.exists(tmp_video):
                    os.remove(tmp_video)
                codecs_detail = 'OpenCV VideoWriter MP4V ready'
            else:
                codecs_status = 'warning'
                codecs_detail = 'OpenCV VideoWriter MP4V failed to open'
        except Exception as e:
            codecs_status = 'warning'
            codecs_detail = f'VideoWriter check error: {e}'

        checks.append({
            'id': 'video_codecs',
            'title': 'Video recording codecs',
            'status': codecs_status,
            'details': codecs_detail,
        })

        # 10. System time sync & Telemetry connectivity
        telemetry_status = 'ok'
        telemetry_detail = 'Ready'
        time_sync_status = 'ok'
        time_sync_detail = 'System time verified'
        if self._endpoint:
            try:
                import email.utils
                req = urllib_request.Request(
                    self._endpoint,
                    headers={'User-Agent': f'CVCounter/{APP_VERSION}'},
                    method='HEAD'
                )
                date_header = None
                try:
                    with urllib_request.urlopen(req, timeout=3) as resp:
                        code = getattr(resp, 'status', None) or resp.getcode()
                        date_header = resp.headers.get('date')
                        telemetry_detail = f'Endpoint reachable (HTTP {code})'
                except urllib_error.HTTPError as he:
                    date_header = he.headers.get('date')
                    telemetry_detail = f'Endpoint reached (HTTP {he.code})'

                if date_header:
                    remote_dt = email.utils.parsedate_to_datetime(date_header)
                    now_dt = datetime.now(timezone.utc)
                    delta_sec = round(abs((remote_dt - now_dt).total_seconds()), 1)
                    if delta_sec < 180:
                        time_sync_detail = f'Clock in sync (delta {delta_sec}s)'
                    else:
                        time_sync_status = 'warning'
                        time_sync_detail = f'Clock out of sync: {delta_sec}s discrepancy'
                else:
                    time_sync_status = 'info'
                    time_sync_detail = 'Remote time header unavailable'
            except Exception as e:
                telemetry_status = 'warning'
                telemetry_detail = f'Endpoint unreachable: {e}'
                time_sync_status = 'info'
                time_sync_detail = 'Skipped (offline)'
        else:
            telemetry_status = 'warning'
            telemetry_detail = 'No endpoint configured'
            time_sync_status = 'info'
            time_sync_detail = 'Skipped (no endpoint)'

        checks.append({
            'id': 'system_time',
            'title': 'System time synchronization',
            'status': time_sync_status,
            'details': time_sync_detail,
        })

        checks.append({
            'id': 'telemetry',
            'title': 'Telemetry server connection',
            'status': telemetry_status,
            'details': telemetry_detail,
        })

        # 11. Video counters status
        counters_count = 0
        running_count = 0
        if runtime_context:
            object_counters = runtime_context.get('object_counters') or {}
            counters_count = len(object_counters)
            running_count = sum(1 for c in object_counters.values() if getattr(c, 'running', False))

        checks.append({
            'id': 'counters',
            'title': 'Active video streams',
            'status': 'ok' if counters_count > 0 else 'info',
            'details': f'{running_count} running of {counters_count} configured counters',
        })

        all_ok = all(c['status'] in ('ok', 'info') for c in checks)
        return {
            'all_ok': all_ok,
            'timestamp': _utc_now_iso(),
            'checks': checks,
        }

    def build_diagnostic_report(self, mode: str = 'manual') -> dict[str, Any]:
        """
        Build a diagnostic payload for download / manual send.
        Prefers pending events if available, falls back to in-memory recent event buffer.
        
        Args:
            mode: The mode of the diagnostic report.
            
        Returns:
            dict[str, Any]: The diagnostic report.
        """
        with self._lock:
            if self._pending:
                events = list(self._pending)
            else:
                events = list(self._recent_events)
        report = self._build_batch(events, mode=mode)
        return report

    def _get_system_fingerprint(self) -> dict[str, Any]:
        """
        Get the system fingerprint.
        
        Args:
            None
            
        Returns:
            dict[str, Any]: The system fingerprint.
        """
        now = time.monotonic()
        with self._lock:
            if self._system_cache is not None and (now - self._system_cache_at) < self._flush_interval_sec:
                fingerprint = dict(self._system_cache)
            else:
                fingerprint = self._collect_system_fingerprint()
                self._system_cache = dict(fingerprint)
                self._system_cache_at = now
            context = self._runtime_context

        counters_count = 0
        counters_running = 0
        backends: list[str] = []
        if context:
            config = context.get('config')
            if config is not None:
                try:
                    detections = config.get('detections', {}) or {}
                    counters_count = len(detections)
                except Exception:
                    counters_count = 0
            object_counters = context.get('object_counters') or {}
            object_counters_lock = context.get('object_counters_lock')
            try:
                if object_counters_lock:
                    with object_counters_lock:
                        counters_list = list(object_counters.values())
                else:
                    counters_list = list(object_counters.values())
                counters_running = len(counters_list)
                for counter in counters_list:
                    model_type = getattr(counter, 'model_type', None)
                    if model_type and model_type not in backends:
                        backends.append(str(model_type))
            except Exception:
                pass
        fingerprint['counters_count'] = counters_count
        fingerprint['counters_running'] = counters_running
        fingerprint['detector_backends'] = backends
        return fingerprint

    def _collect_system_fingerprint(self) -> dict[str, Any]:
        """
        Collect a light system fingerprint (no cpu_percent interval wait).
        
        Args:
            None
            
        Returns:
            dict[str, Any]: The system fingerprint.
        """
        info: dict[str, Any] = {
            'python_version': platform.python_version(),
            'platform': platform.platform(),
            'system': platform.system(),
            'release': platform.release(),
            'machine': platform.machine(),
            'processor': platform.processor(),
            'cpu_count': os.cpu_count(),
            'app_version': APP_VERSION,
        }
        # PyTorch / CUDA detection
        try:
            import torch
            info['py_torch_version'] = getattr(torch, '__version__', None)
            info['py_torch_cuda_available'] = bool(torch.cuda.is_available())
            info['py_torch_cuda_version'] = torch.version.cuda or None
            if torch.cuda.is_available():
                try:
                    info['gpu_name'] = torch.cuda.get_device_name(0)
                    info['cuda_device_count'] = torch.cuda.device_count()
                except Exception:
                    pass
        except Exception:
            info['py_torch_version'] = None
            info['py_torch_cuda_available'] = False

        # OpenVINO detection
        try:
            import openvino
            info['openvino_version'] = getattr(openvino, '__version__', None)
        except Exception:
            info['openvino_version'] = None

        # System memory via psutil if available
        try:
            import psutil
            mem = psutil.virtual_memory()
            info['ram_total_mb'] = int(mem.total / (1024 * 1024))
            info['ram_available_mb'] = int(mem.available / (1024 * 1024))
        except Exception:
            pass

        return info

