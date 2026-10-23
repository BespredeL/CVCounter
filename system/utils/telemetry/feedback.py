# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from .constants import *  # noqa: F401,F403


class FeedbackMixin:
    """Immediate feedback reports sent to the telemetry endpoint."""

    def submit_feedback(
            self,
            comment: str,
            email: str = '',
            include_logs: bool = True,
    ) -> tuple[bool, str]:
        """
        Submit user feedback with optional logs and diagnostics.
        Sends report immediately to the telemetry endpoint.
        
        Args:
            comment: User feedback or bug description.
            email: Optional user email for follow-up.
            include_logs: Whether to attach recent server log lines.
            
        Returns:
            tuple[bool, str]: Success flag and human-readable message.
        """
        clean_comment = str(comment or '').strip()
        if not clean_comment:
            return False, 'Feedback comment cannot be empty'

        logs_content = ''
        if include_logs:
            log_path = resolve_project_path(DEFAULT_LOG_PATH) or DEFAULT_LOG_PATH
            try:
                if os.path.isfile(log_path):
                    with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                        lines = f.readlines()
                    logs_content = ''.join(lines[-80:])
            except Exception as e:
                logs_content = f'Error reading logs: {e}'

        item = {
            '_cmd': _CMD_EVENT,
            'id': str(uuid.uuid4()),
            'ts': _utc_now_iso(),
            'type': 'feedback',
            'name': 'user_feedback',
            'feedback': {
                'comment': clean_comment,
                'email': str(email or '').strip(),
                'logs': logs_content,
            },
            'props': {
                'recent_events_count': len(self._recent_events),
            },
        }

        normalized = self._normalize_event(item)
        with self._lock:
            self._recent_events.append(normalized)

        # Build an immediate single-batch report for user feedback
        report = self._build_batch([normalized], mode='feedback')
        ok, message, status_code = self._post_batch(report)
        self._write_last_send(ok=ok, message=message, status_code=status_code, mode='feedback')
        if not ok:
            # Spill if endpoint is offline
            self._spill_events([normalized])
            return False, message
        return True, 'Feedback submitted successfully'

