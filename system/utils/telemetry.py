# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 26.07.2026
# Updated: 08.10.2026
# Website: https://bespredel.name

from __future__ import annotations

from collections import deque
import hashlib
import hmac
import json
import os
import platform
import queue
import sys
import threading
import time
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from urllib import error as urllib_error
from urllib import request as urllib_request

from system.__version__ import APP_VERSION
from system.utils.paths import ensure_parent_dir, resolve_project_path
from system.utils.telemetry_sanitize import sanitize_props, sanitize_text

SCHEMA_VERSION = 1
DEFAULT_ENDPOINT = 'https://bespredel.name/api/cvcounter/telemetry'
TELEMETRY_DIR = 'storage/telemetry'
INSTALL_ID_FILE = 'storage/telemetry/install_id'
QUEUE_FILE = 'storage/telemetry/queue.jsonl'
LAST_SEND_FILE = 'storage/telemetry/last_send.json'
MAX_QUEUE_DISK_BYTES = 512 * 1024

_CMD_EVENT = 'event'
_CMD_FLUSH = 'flush'
_CMD_MANUAL = 'manual'
_CMD_SHUTDOWN = 'shutdown'


def _utc_now_iso() -> str:
    """
    Return the current UTC time in ISO format.
    
    Returns:
        str: The current UTC time in ISO format.
    """
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _safe_int(value: Any, default: int) -> int:
    """
    Convert a value to an integer, returning the default value if the conversion fails.
    
    Args:
        value: The value to convert to an integer.
        default: The default value to return if the conversion fails.
        
    Returns:
        int: The integer value of the input, or the default value if the conversion fails.
    """
    try:
        parsed = int(value)
        return parsed if parsed >= 1 else default
    except (TypeError, ValueError):
        return default


def _message_hash(message: str) -> str:
    """
    Generate a SHA-256 hash of a message.
    
    Args:
        message: The message to hash.
        
    Returns:
        str: The SHA-256 hash of the message.
    """
    return hashlib.sha256(message.encode('utf-8', errors='replace')).hexdigest()[:16]


class TelemetryManager:
    """
    Singleton fire-and-forget telemetry and diagnostics manager.
    """

    _instance: Optional['TelemetryManager'] = None
    _init_lock = threading.Lock()

    def __new__(cls) -> 'TelemetryManager':
        with cls._init_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if getattr(self, '_initialized', False):
            return
        self._initialized = True
        self._lock = threading.RLock()
        self._enabled = False
        self._send_errors = True
        self._send_usage = True
        self._endpoint = DEFAULT_ENDPOINT
        self._flush_interval_sec = 300
        self._max_batch_size = 50
        self._max_queue_size = 200
        self._max_stack_chars = 8000
        self._error_dedup_sec = 120
        self._timeout_sec = 5
        self._hmac_secret = ''
        self._queue: queue.Queue = queue.Queue(maxsize=200)
        self._worker: Optional[threading.Thread] = None
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._dedup: dict[str, float] = {}
        self._dropped = 0
        self._pending: list[dict[str, Any]] = []
        self._recent_events: deque[dict[str, Any]] = deque(maxlen=100)
        self._system_cache: Optional[dict[str, Any]] = None
        self._system_cache_at = 0.0
        self._runtime_context: Optional[dict[str, Any]] = None
        self._logging_telemetry_error = False
        self._started_at = time.monotonic()
        self._install_id = self._load_or_create_install_id()

    # ------------------------------------------------------------------
    # Configuration / lifecycle
    # ------------------------------------------------------------------

    def configure(self, config_manager: Any, runtime_context: Optional[dict[str, Any]] = None) -> None:
        """
        Apply telemetry settings from ConfigManager and start worker if enabled.
        
        Args:
            config_manager: The ConfigManager instance.
            runtime_context: The runtime context.
            
        Returns:
            None
        """
        telemetry = config_manager.get('telemetry') or {}
        if not isinstance(telemetry, dict):
            telemetry = {}

        with self._lock:
            self._runtime_context = runtime_context
            self._enabled = bool(telemetry.get('enabled', False))
            self._send_errors = bool(telemetry.get('send_errors', True))
            self._send_usage = bool(telemetry.get('send_usage', True))
            endpoint = telemetry.get('endpoint') or DEFAULT_ENDPOINT
            self._endpoint = str(endpoint).strip() or DEFAULT_ENDPOINT
            self._flush_interval_sec = _safe_int(telemetry.get('flush_interval_sec'), 300)
            self._max_batch_size = _safe_int(telemetry.get('max_batch_size'), 50)
            self._max_queue_size = _safe_int(telemetry.get('max_queue_size'), 200)
            self._max_stack_chars = _safe_int(telemetry.get('max_stack_chars'), 8000)
            self._error_dedup_sec = _safe_int(telemetry.get('error_dedup_sec'), 120)
            self._timeout_sec = _safe_int(telemetry.get('timeout_sec'), 5)
            self._hmac_secret = str(telemetry.get('hmac_secret') or '')
            if self._worker is None or not self._worker.is_alive():
                self._queue = queue.Queue(maxsize=self._max_queue_size)

        if self._enabled:
            self._ensure_worker()

    def set_runtime_context(self, runtime_context: Optional[dict[str, Any]]) -> None:
        """
        Set the runtime context.
        
        Args:
            runtime_context: The runtime context.
            
        Returns:
            None
        """
        with self._lock:
            self._runtime_context = runtime_context

    def shutdown(self, timeout: float = 2.0) -> None:
        """
        Best-effort flush and stop worker without blocking the app long.
        
        Args:
            timeout: The timeout in seconds.
            
        Returns:
            None
        """
        if self._worker is None or not self._worker.is_alive():
            return
        self._enqueue_command({'_cmd': _CMD_SHUTDOWN}, force=True)
        self._wake.set()
        self._worker.join(timeout=max(0.1, float(timeout)))
        self._stop.set()

    # ------------------------------------------------------------------
    # Public hot-path API
    # ------------------------------------------------------------------

    def track(self, event: str, props: Optional[dict[str, Any]] = None) -> None:
        """
        Enqueue a usage event. Always keeps a copy in local diagnostic buffer.
        
        Args:
            event: The event name.
            props: The event properties.
            
        Returns:
            None
        """
        name = str(event or '').strip()
        if not name:
            return

        location = str(props.get('location') or '') if props else ''
        reason = str(props.get('reason') or '') if props else ''

        # Rate-limiting: high-frequency stream reconnect/loss uses a short 10s window;
        # other usage events use a 1s debounce to avoid rapid duplicate submissions.
        if name in ('stream_lost', 'stream_reconnected'):
            dedup_key = f'stream:{name}:{location}:{reason}'
            dedup_window = 10.0
        else:
            dedup_key = f'usage:{name}:{location}'
            dedup_window = 1.0

        if not self._allow_dedup(dedup_key, window_sec=dedup_window):
            return

        item = {
            '_cmd': _CMD_EVENT,
            'id': str(uuid.uuid4()),
            'ts': _utc_now_iso(),
            'type': 'usage',
            'name': name,
            'props': dict(props) if props else {},
        }

        # Keep recent event in memory for manual diagnostics even if auto is disabled
        normalized = self._normalize_event(item)
        with self._lock:
            self._recent_events.append(normalized)

        if not self._enabled or not self._send_usage:
            return

        self._enqueue_command(item)

    def capture_exception(
            self,
            exc: Optional[BaseException] = None,
            tags: Optional[dict[str, Any]] = None,
            exc_info: Any = None,
    ) -> None:
        """
        Enqueue an error event. Always keeps a copy in local diagnostic buffer.
        
        Args:
            exc: The exception instance.
            tags: Additional metadata tags.
            exc_info: Exception tuple (type, val, tb) or True.

        Returns:
            None
        """
        if self._logging_telemetry_error:
            return

        exc_type = ''
        message = ''
        stack = ''

        resolved_exc_info = None
        if exc_info is True or (exc_info is None and exc is None):
            cur_sys = sys.exc_info()
            if cur_sys[0] is not None:
                resolved_exc_info = cur_sys
        elif isinstance(exc_info, tuple) and len(exc_info) == 3 and exc_info[0] is not None:
            resolved_exc_info = exc_info

        if resolved_exc_info is not None:
            cur_type, cur_val, cur_tb = resolved_exc_info
            exc_type = getattr(cur_type, '__name__', str(cur_type))
            message = str(cur_val) if cur_val is not None else ''
            try:
                stack = ''.join(traceback.format_exception(cur_type, cur_val, cur_tb))
            except Exception:
                stack = traceback.format_exc()
        elif exc is not None:
            exc_type = type(exc).__name__
            message = str(exc)
            try:
                stack = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            except Exception:
                stack = traceback.format_exc()
        else:
            stack = traceback.format_exc()
            if 'NoneType: None' in stack:
                stack = ''
            exc_type = 'Error'
            message = 'Exception occurred'

        if not exc_type:
            exc_type = 'Error'
        if not message:
            message = exc_type

        dedup_key = f'error:{exc_type}:{_message_hash(message)}'
        if not self._allow_dedup(dedup_key, window_sec=float(self._error_dedup_sec)):
            return

        item = {
            '_cmd': _CMD_EVENT,
            'id': str(uuid.uuid4()),
            'ts': _utc_now_iso(),
            'type': 'error',
            'name': 'uncaught_exception',
            'props': dict(tags) if tags else {},
            'error': {
                'type': exc_type,
                'message': message,
                'stack': stack,
            },
        }

        normalized = self._normalize_event(item)
        with self._lock:
            self._recent_events.append(normalized)

        if not self._enabled or not self._send_errors:
            return

        self._enqueue_command(item)

    def capture_error_message(
            self,
            message: str,
            tags: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Enqueue a non-exception error message (e.g. from logger.error).
        
        Args:
            message: Error description.
            tags: Optional metadata.
            
        Returns:
            None
        """
        if self._logging_telemetry_error:
            return
        msg = str(message or '').strip()
        if not msg:
            return

        dedup_key = f'error:logged_error:{_message_hash(msg)}'
        if not self._allow_dedup(dedup_key, window_sec=float(self._error_dedup_sec)):
            return

        item = {
            '_cmd': _CMD_EVENT,
            'id': str(uuid.uuid4()),
            'ts': _utc_now_iso(),
            'type': 'error',
            'name': 'logged_error',
            'props': dict(tags) if tags else {},
            'error': {
                'type': 'LoggedError',
                'message': msg,
                'stack': '',
            },
        }

        normalized = self._normalize_event(item)
        with self._lock:
            self._recent_events.append(normalized)

        if not self._enabled or not self._send_errors:
            return

        self._enqueue_command(item)

    def request_manual_send(self) -> tuple[bool, str]:
        """
        Queue a manual diagnostic send. Always available (even if auto disabled).
        
        Args:
            None
            
        Returns:
            tuple[bool, str]: A tuple containing a boolean indicating success and a string message.
        """
        if not self._endpoint:
            return False, 'Telemetry endpoint is not configured'

        payload = {
            '_cmd': _CMD_MANUAL,
            'requested_at': _utc_now_iso(),
        }

        if self._enabled:
            self._ensure_worker()
            ok = self._enqueue_command(payload, force=True)
            if not ok:
                return False, 'Telemetry queue is full'
            self._wake.set()
            return True, 'Telemetry send queued'

        thread = threading.Thread(
            target=self._run_manual_oneshot,
            name='TelemetryManualSend',
            daemon=True,
        )
        thread.start()

        return True, 'Telemetry send started'

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

    def export_json_bytes(self) -> bytes:
        """
        Serialize a diagnostic report for download.
        
        Args:
            None
            
        Returns:
            bytes: The serialized diagnostic report.
        """
        report = self.build_diagnostic_report(mode='manual')
        return json.dumps(report, ensure_ascii=False, indent=2).encode('utf-8')

    def get_last_send_status(self) -> Optional[dict[str, Any]]:
        """
        Get the last send status.
        
        Args:
            None
            
        Returns:
            Optional[dict[str, Any]]: The last send status.
        """
        path = resolve_project_path(LAST_SEND_FILE) or LAST_SEND_FILE
        try:
            with open(path, 'r', encoding='utf-8') as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else None
        except (OSError, ValueError, TypeError):
            return None

    def get_queue_status(self) -> dict[str, Any]:
        """
        Return diagnostic status and queue statistics for UI.
        
        Returns:
            dict[str, Any]: Metrics on in-memory and disk queues.
        """
        path = resolve_project_path(QUEUE_FILE) or QUEUE_FILE
        disk_events_count = 0
        disk_bytes = 0
        try:
            if os.path.isfile(path):
                disk_bytes = os.path.getsize(path)
                with open(path, 'r', encoding='utf-8') as handle:
                    disk_events_count = sum(1 for line in handle if line.strip())
        except OSError:
            pass

        with self._lock:
            pending_count = len(self._pending)
            recent_count = len(self._recent_events)

        return {
            'enabled': self._enabled,
            'pending_count': pending_count,
            'recent_count': recent_count,
            'disk_events_count': disk_events_count,
            'disk_bytes': disk_bytes,
            'dropped_count': self._dropped,
            'last_send': self.get_last_send_status(),
        }

    @property
    def enabled(self) -> bool:
        """
        Get the enabled status.
        
        Args:
            None
            
        Returns:
            bool: The enabled status.
        """
        return self._enabled

    @property
    def dropped_count(self) -> int:
        """
        Get the dropped count.
        
        Args:
            None
            
        Returns:
            int: The dropped count.
        """
        return self._dropped

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _allow_dedup(self, key: str, window_sec: Optional[float] = None) -> bool:
        """
        Check if a deduplication key is allowed within the given time window.
        
        Args:
            key: The deduplication key.
            window_sec: Deduplication window in seconds. Defaults to _error_dedup_sec.
            
        Returns:
            bool: True if allowed, False if throttled.
        """
        now = time.monotonic()
        effective_window = float(self._error_dedup_sec) if window_sec is None else float(window_sec)
        with self._lock:
            last = self._dedup.get(key)
            if last is not None and (now - last) < effective_window:
                return False
            self._dedup[key] = now

            if len(self._dedup) > 500:
                cutoff = now - max(effective_window, float(self._error_dedup_sec))
                self._dedup = {k: v for k, v in self._dedup.items() if v >= cutoff}

            return True

    def _enqueue_command(self, item: dict[str, Any], force: bool = False) -> bool:
        """
        Enqueue a command.
        
        Args:
            item: The item to enqueue.
            force: Whether to force the enqueue.
            
        Returns:
            bool: True if the command was enqueued, False otherwise.
        """
        try:
            if force:
                try:
                    self._queue.put_nowait(item)
                except queue.Full:
                    try:
                        self._queue.get_nowait()
                        self._dropped += 1
                    except queue.Empty:
                        pass
                    self._queue.put_nowait(item)
            else:
                self._queue.put_nowait(item)
            self._wake.set()
            return True
        except queue.Full:
            self._dropped += 1
            return False

    def _ensure_worker(self) -> None:
        """
        Ensure a worker thread is running.
        
        Args:
            None
            
        Returns:
            None
        """
        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                return
            self._stop.clear()
            self._worker = threading.Thread(
                target=self._worker_loop,
                name='TelemetryWorker',
                daemon=True,
            )
            self._worker.start()

    def _run_manual_oneshot(self) -> None:
        """
        Run a manual oneshot send when worker is not running.
        
        Args:
            None
            
        Returns:
            None
        """
        try:
            report = self.build_diagnostic_report(mode='manual')
            ok, message, status_code = self._post_batch(report)
            self._write_last_send(ok=ok, message=message, status_code=status_code, mode='manual')
        except Exception as exc:
            self._write_last_send(ok=False, message=str(exc), status_code=None, mode='manual')
            self._log_local(f'Telemetry manual send failed: {exc}')

    def _worker_loop(self) -> None:
        """
        Run the worker loop.
        
        Args:
            None
            
        Returns:
            None
        """
        last_flush = time.monotonic()
        while not self._stop.is_set():
            self._wake.wait(timeout=min(5.0, float(self._flush_interval_sec)))
            self._wake.clear()
            shutdown_requested = False

            while True:
                try:
                    item = self._queue.get_nowait()
                except queue.Empty:
                    break

                cmd = item.get('_cmd')
                if cmd == _CMD_SHUTDOWN:
                    shutdown_requested = True
                elif cmd == _CMD_MANUAL:
                    self._handle_manual_send()
                elif cmd == _CMD_FLUSH:
                    self._flush_pending(mode='auto')
                    last_flush = time.monotonic()
                elif cmd == _CMD_EVENT:
                    normalized = self._normalize_event(item)
                    with self._lock:
                        self._pending.append(normalized)
                    if len(self._pending) >= self._max_batch_size:
                        self._flush_pending(mode='auto')
                        last_flush = time.monotonic()

            if (time.monotonic() - last_flush) >= self._flush_interval_sec:
                self._flush_pending(mode='auto')
                last_flush = time.monotonic()

            if shutdown_requested:
                # Shorten timeout for final flush so shutdown does not block
                old_timeout = self._timeout_sec
                self._timeout_sec = min(2, self._timeout_sec)
                try:
                    self._flush_pending(mode='auto', max_batches=2)
                finally:
                    self._timeout_sec = old_timeout
                with self._lock:
                    if self._pending:
                        self._spill_events(self._pending)
                        self._pending.clear()
                self._stop.set()
                break

    def _normalize_event(self, item: dict[str, Any]) -> dict[str, Any]:
        """
        Normalize an event.
        
        Args:
            item: The item to normalize.
            
        Returns:
            dict[str, Any]: The normalized event.
        """
        max_stack = self._max_stack_chars
        event = {
            'id': item.get('id') or str(uuid.uuid4()),
            'ts': item.get('ts') or _utc_now_iso(),
            'type': item.get('type') or 'usage',
            'name': item.get('name') or 'unknown',
            'props': sanitize_props(item.get('props')),
        }
        error = item.get('error')
        if isinstance(error, dict):
            event['error'] = {
                'type': sanitize_text(str(error.get('type') or ''), max_chars=200),
                'message': sanitize_text(str(error.get('message') or ''), max_chars=1000),
                'stack': sanitize_text(str(error.get('stack') or ''), max_chars=max_stack),
            }
        return event

    def _handle_manual_send(self) -> None:
        """
        Handle a manual send.
        
        Args:
            None
            
        Returns:
            None
        """
        report = self.build_diagnostic_report(mode='manual')
        with self._lock:
            self._pending.clear()
        ok, message, status_code = self._post_batch(report)
        self._write_last_send(ok=ok, message=message, status_code=status_code, mode='manual')

    def _flush_pending(self, mode: str = 'auto', max_batches: int = 5) -> None:
        """
        Flush pending events in batches.
        
        Args:
            mode: The mode of the flush ('auto', 'manual').
            max_batches: Maximum number of batches to send in one run.
            
        Returns:
            None
        """
        with self._lock:
            if not self._pending:
                return
            if mode == 'auto' and not self._enabled:
                self._pending.clear()
                return

        batches_sent = 0
        while batches_sent < max_batches:
            with self._lock:
                if not self._pending:
                    break
                batch_events = self._pending[: self._max_batch_size]
                self._pending = self._pending[self._max_batch_size:]

            report = self._build_batch(batch_events, mode=mode)
            ok, message, status_code = self._post_batch(report)
            self._write_last_send(ok=ok, message=message, status_code=status_code, mode=mode)
            batches_sent += 1

            if not ok:
                self._spill_events(batch_events)
                break
            else:
                # Connection is healthy, replay any previously spilled events
                self._replay_spilled_events()

    def _replay_spilled_events(self) -> None:
        """
        Replay events previously spilled to QUEUE_FILE when network was down.
        """
        path = resolve_project_path(QUEUE_FILE) or QUEUE_FILE
        try:
            if not os.path.isfile(path) or os.path.getsize(path) == 0:
                return
            with open(path, 'r', encoding='utf-8') as handle:
                lines = handle.readlines()
        except OSError:
            return

        if not lines:
            return

        replayed_events: list[dict[str, Any]] = []
        remaining_lines: list[str] = []
        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
            if len(replayed_events) < self._max_batch_size:
                try:
                    replayed_events.append(json.loads(line_str))
                except Exception:
                    continue
            else:
                remaining_lines.append(line)

        if not replayed_events:
            try:
                with open(path, 'w', encoding='utf-8'):
                    pass
            except OSError:
                pass
            return

        report = self._build_batch(replayed_events, mode='replay')
        ok, message, status_code = self._post_batch(report)
        if ok:
            try:
                ensure_parent_dir(path)
                tmp_path = f"{path}.tmp"
                with open(tmp_path, 'w', encoding='utf-8') as handle:
                    for rem in remaining_lines:
                        handle.write(rem if rem.endswith('\n') else rem + '\n')
                os.replace(tmp_path, path)
            except OSError:
                pass

    def _build_batch(self, events: list[dict[str, Any]], mode: str) -> dict[str, Any]:
        """
        Build a batch of events.
        
        Args:
            events: The events to build the batch from.
            mode: The mode of the batch.
            
        Returns:
            dict[str, Any]: The batch of events.
        """
        return {
            'schema_version': SCHEMA_VERSION,
            'sent_at': _utc_now_iso(),
            'install_id': self._install_id,
            'app_version': APP_VERSION,
            'mode': mode,
            'system': self._get_system_fingerprint(),
            'events': events,
            'meta': {
                'dropped': self._dropped,
                'uptime_sec': int(time.monotonic() - self._started_at),
            },
        }

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

    def _post_batch(self, report: dict[str, Any]) -> tuple[bool, str, Optional[int]]:
        """
        Post a batch of events.
        
        Args:
            report: The report to post.
            
        Returns:
            tuple[bool, str, Optional[int]]: A tuple containing a boolean indicating success, a string message, and an optional status code.
        """
        body = json.dumps(report, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': f'CVCounter/{APP_VERSION}',
            'X-CVCounter-App-Version': APP_VERSION,
            'X-CVCounter-Install-Id': self._install_id,
        }
        if self._hmac_secret:
            digest = hmac.new(
                self._hmac_secret.encode('utf-8'),
                body,
                hashlib.sha256,
            ).hexdigest()
            headers['X-CVCounter-Signature'] = f'sha256={digest}'

        req = urllib_request.Request(
            self._endpoint,
            data=body,
            headers=headers,
            method='POST',
        )
        try:
            with urllib_request.urlopen(req, timeout=self._timeout_sec) as response:
                status = getattr(response, 'status', None) or response.getcode()
                if 200 <= int(status) < 300:
                    return True, 'ok', int(status)
                return False, f'HTTP {status}', int(status)
        except urllib_error.HTTPError as exc:
            return False, f'HTTP {exc.code}', int(exc.code)
        except Exception as exc:
            self._log_local(f'Telemetry POST failed: {exc}')
            return False, str(exc), None

    def _spill_events(self, events: list[dict[str, Any]]) -> None:
        """
        Spill events to a file.
        
        Args:
            events: The events to spill.
            
        Returns:
            None
        """
        path = resolve_project_path(QUEUE_FILE) or QUEUE_FILE
        try:
            ensure_parent_dir(path)
            if os.path.exists(path) and os.path.getsize(path) > MAX_QUEUE_DISK_BYTES:
                with open(path, 'w', encoding='utf-8'):
                    pass
            with open(path, 'a', encoding='utf-8') as handle:
                for event in events:
                    handle.write(json.dumps(event, ensure_ascii=False) + '\n')
        except OSError:
            pass

    def _write_last_send(
            self,
            ok: bool,
            message: str,
            status_code: Optional[int],
            mode: str,
    ) -> None:
        """
        Write the last send status atomically.
        
        Args:
            ok: Whether the last send was successful.
            message: The message of the last send.
            status_code: The status code of the last send.
            mode: The mode of the last send.
            
        Returns:
            None
        """
        path = resolve_project_path(LAST_SEND_FILE) or LAST_SEND_FILE
        payload = {
            'ok': ok,
            'message': sanitize_text(message, max_chars=500),
            'status_code': status_code,
            'mode': mode,
            'sent_at': _utc_now_iso(),
        }
        try:
            ensure_parent_dir(path)
            tmp_path = f"{path}.tmp"
            with open(tmp_path, 'w', encoding='utf-8') as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
            os.replace(tmp_path, path)
        except OSError:
            try:
                with open(path, 'w', encoding='utf-8') as handle:
                    json.dump(payload, handle, ensure_ascii=False, indent=2)
            except OSError:
                pass

    def _load_or_create_install_id(self) -> str:
        """
        Load or create an install ID.
        
        Args:
            None
            
        Returns:
            str: The install ID.
        """
        path = resolve_project_path(INSTALL_ID_FILE) or INSTALL_ID_FILE
        try:
            if os.path.isfile(path):
                with open(path, 'r', encoding='utf-8') as handle:
                    value = handle.read().strip()
                if value:
                    return value
        except OSError:
            pass
        install_id = str(uuid.uuid4())
        try:
            ensure_parent_dir(path)
            with open(path, 'w', encoding='utf-8') as handle:
                handle.write(install_id)
        except OSError:
            pass
        return install_id

    def _log_local(self, message: str) -> None:
        """
        Log a message locally.
        
        Args:
            message: The message to log.
            
        Returns:
            None
        """
        if self._logging_telemetry_error:
            return
        self._logging_telemetry_error = True
        try:
            from system.utils.logger import Logger
            Logger().warning(message)
        except Exception:
            pass
        finally:
            self._logging_telemetry_error = False


def get_telemetry() -> TelemetryManager:
    """
    Return the process-wide TelemetryManager singleton.
    
    Args:
        None
            
    Returns:
        TelemetryManager: The TelemetryManager singleton.
    """
    return TelemetryManager()
