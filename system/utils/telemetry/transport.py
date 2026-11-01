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
            ok = self._enqueue_command(payload, force=True)
            if not ok:
                return False, 'Telemetry queue is full'
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
            result = self._post_batch(report)
            self._write_last_send(result, 'manual', event_count=len(report['events']))
        except Exception as exc:
            self._write_last_send(self._post_error(exc), 'manual')
            self._log_local(f'Telemetry manual send failed: {exc}')

    def _handle_manual_send(self) -> None:
        """
        Send the events still waiting for delivery.
        
        Already delivered events are not resent: the report is built from the pending buffer
        only, and the spilled backlog is replayed once the endpoint answers.
        
        Args:
            None
            
        Returns:
            None
        """
        with self._lock:
            pending_events = list(self._pending)
            self._pending.clear()

        if pending_events:
            report = self._build_batch(pending_events, mode='manual')
            result = self._post_batch(report)
            self._write_last_send(result, 'manual', event_count=len(pending_events))
            if not result.ok:
                self._spill_events(pending_events)
                return

        self._replay_spilled_events(max_batches=2)

    @staticmethod
    def _post_error(exc: BaseException) -> PostResult:
        """
        Describe a failure that happened before or during a POST request.
        
        Args:
            exc: The exception raised by the caller.
            
        Returns:
            PostResult: A retryable failure result with no status code.
        """
        return PostResult(False, str(exc), None, 'retry', None, 0, 0)

    def _post_batch(self, report: dict[str, Any]) -> PostResult:
        """
        Post a batch of events.
        
        Args:
            report: The report to post.
            
        Returns:
            PostResult: Outcome, failure verdict, server-requested delay, latency and body size.
        """
        body = json.dumps(report, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': f'CVCounter/{APP_VERSION}',
            'X-CVCounter-App-Version': APP_VERSION,
            'X-CVCounter-Install-Id': self._install_id,
        }
        if getattr(self, '_compress', False):
            compressed_body = gzip.compress(body)
            if len(compressed_body) < len(body):
                body = compressed_body
                headers['Content-Encoding'] = 'gzip'

        if self._hmac_secret:
            digest = hmac.new(
                self._hmac_secret.encode('utf-8'),
                body,
                hashlib.sha256,
            ).hexdigest()
            headers['X-CVCounter-Signature'] = f'sha256={digest}'

        body_size = len(body)
        batch_id = (report.get('meta') or {}).get('batch_id')
        if batch_id:
            headers['X-CVCounter-Batch-Id'] = str(batch_id)

        req = urllib_request.Request(
            self._endpoint,
            data=body,
            headers=headers,
            method='POST',
        )
        started = time.monotonic()
        try:
            with urllib_request.urlopen(req, timeout=self._timeout_sec) as response:
                status = int(getattr(response, 'status', None) or response.getcode())
                latency_ms = self._elapsed_ms(started)
                if 200 <= status < 300:
                    return PostResult(True, 'ok', status, 'sent', None, latency_ms, body_size)
                return PostResult(
                    False,
                    f'HTTP {status}',
                    status,
                    _classify_post_failure(status),
                    self._retry_after(response.headers),
                    latency_ms,
                    body_size,
                )
        except urllib_error.HTTPError as exc:
            err_msg = f'HTTP {exc.code}'
            try:
                err_detail = exc.read(300).decode('utf-8', errors='replace').strip()
                if err_detail:
                    err_msg = f'{err_msg}: {err_detail}'
            except Exception:
                pass
            return PostResult(
                False,
                err_msg,
                int(exc.code),
                _classify_post_failure(int(exc.code)),
                self._retry_after(exc.headers),
                self._elapsed_ms(started),
                body_size,
            )
        except Exception as exc:
            self._log_local(f'Telemetry POST failed: {exc}')
            return PostResult(
                False,
                str(exc),
                None,
                _classify_post_failure(None),
                None,
                self._elapsed_ms(started),
                body_size,
            )

    @staticmethod
    def _elapsed_ms(started: float) -> int:
        """
        Milliseconds spent since a monotonic timestamp.
        
        Args:
            started: Value returned by time.monotonic() when the request began.
            
        Returns:
            int: Elapsed milliseconds.
        """
        return int((time.monotonic() - started) * 1000)

    @staticmethod
    def _retry_after(headers: Any) -> Optional[float]:
        """
        Read how long the server asks to wait before the next attempt.
        
        Args:
            headers: Response headers, or None when the request never reached the server.
            
        Returns:
            Optional[float]: Delay in seconds, or None when the header is absent or unparsable.
        """
        if headers is None:
            return None
        raw = headers.get('Retry-After') if hasattr(headers, 'get') else None
        if not raw:
            return None
        text = str(raw).strip()
        try:
            seconds = float(text)
        except ValueError:
            try:
                import email.utils
                target = email.utils.parsedate_to_datetime(text)
                seconds = (target - datetime.now(timezone.utc)).total_seconds()
            except Exception:
                return None
        if seconds < 0:
            return None
        return min(max(seconds, 1.0), float(MAX_FLUSH_INTERVAL_SEC))

    def _write_last_send(self, result: PostResult, mode: str, event_count: int = 0) -> None:
        """
        Write the last send status atomically and append it to the delivery history.
        
        Args:
            result: Outcome of the POST request.
            mode: The mode of the last send.
            event_count: How many events the batch carried.
            
        Returns:
            None
        """
        path = resolve_project_path(LAST_SEND_FILE) or LAST_SEND_FILE
        payload = {
            'ok': result.ok,
            'message': sanitize_text(result.message, max_chars=500),
            'status_code': result.status_code,
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

        self._append_delivery_record(result, mode, event_count)

    def get_delivery_history(self, limit: int = 5) -> list[dict[str, Any]]:
        """
        Read the most recent delivery attempts, newest first.
        
        Args:
            limit: How many records to return.
            
        Returns:
            list[dict[str, Any]]: Delivery records, empty when no history was kept.
        """
        path = resolve_project_path(DELIVERY_FILE) or DELIVERY_FILE
        try:
            with self._lock:
                if not os.path.isfile(path):
                    return []
                with open(path, 'r', encoding='utf-8', errors='replace') as handle:
                    raw_lines = handle.readlines()
        except OSError:
            return []

        records: list[dict[str, Any]] = []
        for line in reversed(raw_lines):
            line_str = line.strip()
            if not line_str:
                continue
            try:
                parsed = json.loads(line_str)
            except ValueError:
                continue
            if isinstance(parsed, dict):
                records.append(parsed)
            if len(records) >= max(1, int(limit)):
                break
        return records

    def _append_delivery_record(self, result: PostResult, mode: str, event_count: int) -> None:
        """
        Keep a short rolling history of delivery attempts for the diagnostics page.
        
        Args:
            result: Outcome of the POST request.
            mode: The mode of the last send.
            event_count: How many events the batch carried.
            
        Returns:
            None
        """
        path = resolve_project_path(DELIVERY_FILE) or DELIVERY_FILE
        record = {
            'ts': _utc_now_iso(),
            'ok': result.ok,
            'status': result.status_code,
            'mode': mode,
            'events': event_count,
            'bytes': result.bytes,
            'latency_ms': result.latency_ms,
            'next_retry_at': self._next_send_iso(),
        }
        try:
            with self._lock:
                ensure_parent_dir(path)
                with open(path, 'a', encoding='utf-8') as handle:
                    handle.writelines(json.dumps(record, ensure_ascii=False) + '\n')
                self._trim_jsonl(path, max_lines=MAX_DELIVERY_LINES)
        except OSError:
            pass

