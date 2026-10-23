# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from .constants import *  # noqa: F401,F403


class EventCaptureMixin:
    """Usage and error events kept in memory and queued for delivery."""

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

    def capture_client_error(
            self,
            message: str,
            url: str = '',
            line: int = 0,
            col: int = 0,
            stack: str = '',
            breadcrumbs: Optional[list] = None,
    ) -> None:
        """
        Capture a client-side JavaScript error reported by the browser.
        
        Args:
            message: Error message.
            url: Page or script URL where the error occurred.
            line: Line number.
            col: Column number.
            stack: JavaScript call stack string.
            breadcrumbs: Optional recent client-side action breadcrumbs.
            
        Returns:
            None
        """
        msg = str(message or '').strip()
        if not msg:
            return

        dedup_key = f'client_error:{_message_hash(msg)}:{url}:{line}'
        if not self._allow_dedup(dedup_key, window_sec=float(self._error_dedup_sec)):
            return

        clean_breadcrumbs = []
        if isinstance(breadcrumbs, list):
            for b in breadcrumbs[-15:]:
                if isinstance(b, dict):
                    clean_breadcrumbs.append(sanitize_props(b))

        item = {
            '_cmd': _CMD_EVENT,
            'id': str(uuid.uuid4()),
            'ts': _utc_now_iso(),
            'type': 'error',
            'name': 'client_javascript_error',
            'props': {
                'url': sanitize_text(url, max_chars=300),
                'line': int(line) if line else 0,
                'col': int(col) if col else 0,
                'breadcrumbs': clean_breadcrumbs,
            },
            'error': {
                'type': 'JavaScriptError',
                'message': sanitize_text(msg, max_chars=1000),
                'stack': sanitize_text(stack, max_chars=self._max_stack_chars),
            },
        }

        normalized = self._normalize_event(item)
        with self._lock:
            self._recent_events.append(normalized)

        if not self._enabled or not self._send_errors:
            return

        self._enqueue_command(item)

    def track_performance(self, props: dict[str, Any]) -> None:
        """
        Record a stream / detection performance metric event.
        
        Args:
            props: Dictionary of performance stats (FPS, inference time, etc.).
            
        Returns:
            None
        """
        self.track('stream_performance', props)

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
        feedback = item.get('feedback')
        if isinstance(feedback, dict):
            event['feedback'] = {
                'comment': sanitize_text(str(feedback.get('comment') or ''), max_chars=2000),
                'email': sanitize_text(str(feedback.get('email') or ''), max_chars=120),
                'logs': sanitize_text(str(feedback.get('logs') or ''), max_chars=12000),
            }
        return event

