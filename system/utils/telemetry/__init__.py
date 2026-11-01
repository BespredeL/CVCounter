# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from .constants import *  # noqa: F401,F403
from .doctor import DoctorMixin
from .events import EventCaptureMixin
from .feedback import FeedbackMixin
from .transport import TransportMixin
from .worker import QueueWorkerMixin

__all__ = ['TelemetryManager', 'get_telemetry']


class TelemetryManager(
    EventCaptureMixin,
    FeedbackMixin,
    DoctorMixin,
    QueueWorkerMixin,
    TransportMixin,
):
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
        self._enabled = True
        self._send_errors = True
        self._send_usage = True
        self._endpoint = DEFAULT_ENDPOINT
        self._flush_interval_sec = 3600
        self._max_batch_size = 200
        self._max_queue_size = 400
        self._max_stack_chars = 8000
        self._error_dedup_sec = 600
        self._timeout_sec = 10
        self._hmac_secret = ''
        self._compress = True
        self._queue: queue.Queue = queue.Queue(maxsize=400)
        self._worker: Optional[threading.Thread] = None
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._dedup: dict[str, float] = {}
        self._dropped = 0
        self._dropped_window = 0
        self._loop_errors = 0
        self._restarts = 0
        self._restart_streak = 0
        self._restart_streak_at: Optional[float] = None
        self._restart_blocked_until = 0.0
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
            self._enabled = bool(telemetry.get('enabled', True))
            self._send_errors = bool(telemetry.get('send_errors', True))
            self._send_usage = bool(telemetry.get('send_usage', True))
            endpoint = telemetry.get('endpoint') or DEFAULT_ENDPOINT
            self._endpoint = str(endpoint).strip() or DEFAULT_ENDPOINT
            self._flush_interval_sec = _safe_int(telemetry.get('flush_interval_sec'), 3600)
            self._max_batch_size = _safe_int(telemetry.get('max_batch_size'), 200)
            self._max_queue_size = _safe_int(telemetry.get('max_queue_size'), 400)
            self._max_stack_chars = _safe_int(telemetry.get('max_stack_chars'), 8000)
            self._error_dedup_sec = _safe_int(telemetry.get('error_dedup_sec'), 600)
            self._timeout_sec = _safe_int(telemetry.get('timeout_sec'), 10)
            self._hmac_secret = str(telemetry.get('hmac_secret') or '')
            self._compress = bool(telemetry.get('compress', True))
            if self._worker is None or not self._worker.is_alive():
                self._queue = queue.Queue(maxsize=self._max_queue_size)

        if self._enabled:
            with self._lock:
                self._stop.clear()
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

        quarantine_path = resolve_project_path(QUARANTINE_FILE) or QUARANTINE_FILE
        quarantine_count = 0
        try:
            if os.path.isfile(quarantine_path):
                with open(quarantine_path, 'r', encoding='utf-8') as handle:
                    quarantine_count = sum(1 for line in handle if line.strip())
        except OSError:
            pass

        with self._lock:
            pending_count = len(self._pending)
            recent_count = len(self._recent_events)
            dropped_count = self._dropped
            dropped_window = self._dropped_window
            loop_errors = self._loop_errors
            restarts = self._restarts

        worker = self._worker
        return {
            'enabled': self._enabled,
            'pending_count': pending_count,
            'recent_count': recent_count,
            'disk_events_count': disk_events_count,
            'disk_bytes': disk_bytes,
            'quarantine_count': quarantine_count,
            'dropped_count': dropped_count,
            'dropped_window': dropped_window,
            'worker_alive': bool(worker is not None and worker.is_alive()),
            'loop_errors': loop_errors,
            'restarts': restarts,
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
