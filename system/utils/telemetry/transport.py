# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from .constants import *  # noqa: F401,F403


class TransportMixin:
    """HTTP delivery of telemetry batches and manual sends."""

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

