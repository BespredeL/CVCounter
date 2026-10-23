# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from .constants import *  # noqa: F401,F403


class QueueWorkerMixin:
    """Background queue, disk spill, and batch flush."""

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

