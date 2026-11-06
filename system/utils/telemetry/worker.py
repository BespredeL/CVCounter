# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from .constants import *


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
        if self._enabled:
            # Producers rely on this: a worker that died mid-life is revived by the next event.
            self._ensure_worker()
        try:
            if force:
                try:
                    self._queue.put_nowait(item)
                except queue.Full:
                    try:
                        self._queue.get_nowait()
                        self._bump_dropped()
                    except queue.Empty:
                        pass
                    self._queue.put_nowait(item)
            else:
                self._queue.put_nowait(item)
            self._wake.set()
            return True
        except queue.Full:
            self._bump_dropped()
            return False

    def _bump_dropped(self, count: int = 1) -> None:
        """
        Count events lost to a full queue, file rotation or an unusable record.

        Args:
            count: How many events were lost.

        Returns:
            None
        """
        if count <= 0:
            return
        with self._lock:
            self._dropped += count
            self._dropped_window += count

    def _on_send_success(self) -> None:
        """
        Forget per-window losses once the endpoint accepted a batch.

        Args:
            None

        Returns:
            None
        """
        with self._lock:
            self._dropped_window = 0

    def _note_loop_error(self, exc: Exception) -> None:
        """
        Record a worker failure that was survived, without re-raising into the thread.

        Args:
            exc: The exception that interrupted the iteration.

        Returns:
            None
        """
        with self._lock:
            self._loop_errors += 1
        self._log_local(f'Telemetry worker error: {exc!r}')

    def _send_allowed(self, now: Optional[float] = None) -> bool:
        """
        Check whether the endpoint may be contacted again.

        Args:
            now: Monotonic timestamp to test, or None for the current moment.

        Returns:
            bool: True when no backoff delay is active.
        """
        moment = time.monotonic() if now is None else now
        with self._lock:
            return moment >= self._next_send_at

    def _send_delay_sec(self) -> float:
        """
        Seconds left before the next send is allowed.

        Args:
            None

        Returns:
            float: Remaining backoff delay, 0.0 when free to send.
        """
        with self._lock:
            return max(0.0, self._next_send_at - time.monotonic())

    def _next_send_iso(self) -> Optional[str]:
        """
        ISO timestamp of the earliest allowed next send, for the delivery history.

        Args:
            None

        Returns:
            Optional[str]: The delayed timestamp, or None when sending is not held back.
        """
        delay = self._send_delay_sec()
        if delay <= 0:
            return None
        return _utc_iso_in(delay)

    def _apply_backoff(self, result: PostResult) -> None:
        """
        Hold the next attempt back after a temporary failure, or clear the hold on success.

        Args:
            result: Outcome of the batch POST request.

        Returns:
            None
        """
        failures = 0
        with self._lock:
            if result.ok:
                self._backoff_sec = 0.0
                self._consecutive_failures = 0
                self._next_send_at = 0.0
                return

            if result.verdict != 'retry':
                # A batch the endpoint rejects outright is quarantined, not waited for
                self._backoff_sec = 0.0
                self._consecutive_failures = 0
                self._next_send_at = 0.0
                return

            self._consecutive_failures += 1
            failures = self._consecutive_failures
            if result.retry_after is not None:
                delay = float(result.retry_after)
            else:
                base = BACKOFF_START_SEC * (2 ** min(failures - 1, 8))
                delay = min(base, BACKOFF_MAX_SEC)
                delay *= random.uniform(1.0 - BACKOFF_JITTER_RATIO, 1.0 + BACKOFF_JITTER_RATIO)
            self._backoff_sec = delay
            self._next_send_at = time.monotonic() + delay

        if failures >= DELIVERY_FAILURE_REPORT_AFTER:
            # An outage this long is worth a line in the batch instead of only a local log entry
            if hasattr(self, 'capture_delivery_failure'):
                self.capture_delivery_failure(result.status_code, failures, delay)

    def _checkpoint_interval_sec(self) -> float:
        """
        How often the in-memory buffer is mirrored to the disk queue.

        Args:
            None

        Returns:
            float: Checkpoint interval in seconds.
        """
        return max(30.0, min(CHECKPOINT_MAX_SEC, float(self._flush_interval_sec) / 6.0))

    def _schedule_jitter_sec(self) -> float:
        """
        Spread the periodic schedule so installs do not POST in the same second.

        Args:
            None

        Returns:
            float: Offset in seconds, within the configured ratio of the flush interval.
        """
        ratio = SCHEDULE_JITTER_RATIO * random.uniform(-1.0, 1.0)
        return ratio * float(self._flush_interval_sec)

    def _reschedule_flush(self) -> float:
        """
        Monotonic deadline of the next scheduled flush.

        Args:
            None

        Returns:
            float: The timestamp the next automatic flush is due at.
        """
        return time.monotonic() + float(self._flush_interval_sec) + self._schedule_jitter_sec()

    def _checkpoint_pending(self) -> None:
        """
        Mirror buffered events to the disk queue so a killed process does not lose them.

        Args:
            None

        Returns:
            None
        """
        if not self._enabled:
            return
        with self._lock:
            if not self._pending:
                return
            events = list(self._pending)
            self._pending.clear()
        self._spill_events(events)

    def _checkpoint_on_exit(self) -> None:
        """
        Mirror buffered events to disk when the interpreter shuts down.

        Args:
            None

        Returns:
            None
        """
        try:
            self._checkpoint_pending()
        except Exception:
            pass

    def _ensure_worker(self) -> None:
        """
        Ensure a worker thread is running, throttling repeated restarts.
        
        Args:
            None
            
        Returns:
            None
        """
        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                return
            if self._stop.is_set():
                return
            now = time.monotonic()
            if now < self._restart_blocked_until:
                return
            if self._restart_streak_at is None or (now - self._restart_streak_at) > WORKER_RESTART_WINDOW_SEC:
                self._restart_streak_at = now
                self._restart_streak = 0
            self._restart_streak += 1
            self._restarts += 1
            if self._restart_streak >= WORKER_RESTART_LIMIT:
                # A loop that dies at once would otherwise be restarted on every event
                self._restart_blocked_until = now + WORKER_RESTART_COOLDOWN_SEC
                self._restart_streak_at = None
                self._log_local(
                    f'Telemetry worker restarted {self._restart_streak} times within '
                    f'{WORKER_RESTART_WINDOW_SEC:.0f}s, next attempt in '
                    f'{WORKER_RESTART_COOLDOWN_SEC:.0f}s'
                )
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
        Run the worker loop, keeping the thread alive across per-iteration failures.
        
        Args:
            None
            
        Returns:
            None
        """
        next_flush_at = self._reschedule_flush()
        next_checkpoint_at = time.monotonic() + self._checkpoint_interval_sec()
        last_heartbeat = time.monotonic()
        if self._enabled:
            self._replay_spilled_events(max_batches=1)
            # The startup backlog is delivered first; the doctor reads the database and imports
            # torch, so it must not compete with the application coming up around this thread.
            self._doctor_summary_due = True
        while not self._stop.is_set():
            shutdown_requested = False
            try:
                self._wake.wait(timeout=min(30.0, float(self._flush_interval_sec)))
                self._wake.clear()

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
                        next_flush_at = self._reschedule_flush()
                    elif cmd == _CMD_EVENT:
                        normalized = self._normalize_event(item)
                        with self._lock:
                            self._pending.append(normalized)
                            buffered = len(self._pending)
                        if buffered >= self._max_batch_size and self._send_allowed():
                            self._flush_pending(mode='auto')
                            next_flush_at = self._reschedule_flush()

                now = time.monotonic()
                if (now - last_heartbeat) >= 86400:
                    if hasattr(self, 'track_heartbeat'):
                        self.track_heartbeat()
                    # Daily uptime is also when the subsystem summary is worth sending again
                    self._doctor_summary_due = True
                    last_heartbeat = now

                if self._doctor_summary_due and self._send_allowed(now):
                    self._doctor_summary_due = False
                    if hasattr(self, 'track_doctor_summary'):
                        self.track_doctor_summary()

                if now >= next_checkpoint_at:
                    next_checkpoint_at = now + self._checkpoint_interval_sec()
                    self._checkpoint_pending()

                if now >= next_flush_at and self._send_allowed(now):
                    next_flush_at = self._reschedule_flush()
                    self._flush_pending(mode='auto')
            except Exception as exc:
                self._note_loop_error(exc)

            if shutdown_requested:
                # Shorten timeout for final flush so shutdown does not block
                old_timeout = self._timeout_sec
                self._timeout_sec = min(2, self._timeout_sec)
                try:
                    self._flush_pending(mode='auto', max_batches=2, replay_batches=1)
                except Exception as exc:
                    self._note_loop_error(exc)
                finally:
                    self._timeout_sec = old_timeout
                with self._lock:
                    if self._pending:
                        self._spill_events(self._pending)
                        self._pending.clear()
                self._stop.set()
                break

    def _flush_pending(self, mode: str = 'auto', max_batches: int = 5, replay_batches: int = 10) -> None:
        """
        Flush pending events in batches.
        
        Args:
            mode: The mode of the flush ('auto', 'manual').
            max_batches: Maximum number of batches to send in one run.
            replay_batches: Maximum number of spilled batches to send in this run.
            
        Returns:
            None
        """
        with self._lock:
            if mode == 'auto' and not self._enabled:
                self._pending.clear()
                return
            has_pending = bool(self._pending)

        if not has_pending:
            if mode == 'auto' and self._enabled:
                self._replay_spilled_events(max_batches=replay_batches)
            return

        batches_sent = 0
        while batches_sent < max_batches:
            with self._lock:
                if not self._pending:
                    break
                batch_events = self._pending[: self._max_batch_size]
                self._pending = self._pending[self._max_batch_size:]

            report = self._build_batch(batch_events, mode=mode)
            result = self._post_batch(report)
            self._apply_backoff(result)
            self._write_last_send(result, mode, event_count=len(batch_events))
            batches_sent += 1

            if result.ok:
                self._on_send_success()
                # Connection is healthy, replay any previously spilled events
                self._replay_spilled_events(max_batches=replay_batches)
                continue

            if result.status_code == 413:
                # Too large for the endpoint: replay will retry it in smaller batches
                self._spill_events(batch_events)
                break

            if result.verdict == 'permfail':
                # The endpoint keeps rejecting this batch; spilling it would block the queue
                self._quarantine_records([(MAX_SPILL_ATTEMPTS, event) for event in batch_events])
                continue

            self._spill_events(batch_events)
            break

    def _replay_spilled_events(self, max_batches: int = 10) -> None:
        """
        Replay events previously spilled to QUEUE_FILE when network was down.

        Batches the endpoint permanently rejects move to QUARANTINE_FILE so the rest of the
        backlog still gets delivered; a transport failure stops the pass with the file intact.

        Args:
            max_batches: Maximum number of batches sent in one replay pass.

        Returns:
            None
        """
        path = resolve_project_path(QUEUE_FILE) or QUEUE_FILE
        try:
            with self._lock:
                if not os.path.isfile(path) or os.path.getsize(path) == 0:
                    return
                with open(path, 'r', encoding='utf-8') as handle:
                    raw_lines = handle.readlines()
        except OSError:
            return

        records: list[tuple[int, dict[str, Any]]] = []
        unreadable = 0
        for line in raw_lines:
            line_str = line.strip()
            if not line_str:
                continue
            attempts, event = _read_spill_record(line_str)
            if event is None:
                unreadable += 1
                continue
            records.append((attempts, event))

        seen_ids = {str(event.get('id') or '') for _attempts, event in records}
        if unreadable or not records:
            self._bump_dropped(unreadable)
            self._write_spill_records(records, seen_ids)
        if not records:
            return

        cursor = 0
        batch_limit = self._max_batch_size
        batches_sent = 0
        while batches_sent < max_batches and cursor < len(records):
            chunk = records[cursor: cursor + batch_limit]
            report = self._build_batch([event for _attempts, event in chunk], mode='replay')
            result = self._post_batch(report)
            self._apply_backoff(result)
            self._append_delivery_record(result, 'replay', event_count=len(chunk))

            if result.ok:
                self._on_send_success()
                cursor += len(chunk)
                batches_sent += 1
                records = records[cursor:]
                cursor = 0
                self._write_spill_records(records, seen_ids)
                continue

            if result.verdict == 'retry':
                return

            if result.status_code == 413 and batch_limit > 1:
                batch_limit = max(1, batch_limit // 2)
                continue

            kept: list[tuple[int, dict[str, Any]]] = []
            dead: list[tuple[int, dict[str, Any]]] = []
            for attempts, event in chunk:
                (dead if attempts + 1 >= MAX_SPILL_ATTEMPTS else kept).append((attempts + 1, event))
            self._quarantine_records(dead)

            # Records that stay in the queue are written back, but not re-sent in this pass
            records = kept + records[cursor + len(chunk):]
            cursor = len(kept)
            batches_sent += 1
            self._write_spill_records(records, seen_ids)

    def _load_location_aliases(self) -> dict[str, str]:
        """
        Read the local alias to label map so camera history survives a restart.

        Args:
            None

        Returns:
            dict[str, str]: Known aliases and the labels they stand for.
        """
        path = resolve_project_path(LOCATIONS_FILE) or LOCATIONS_FILE
        try:
            with open(path, 'r', encoding='utf-8') as handle:
                stored = json.load(handle)
        except (OSError, ValueError):
            return {}
        if not isinstance(stored, dict):
            return {}
        return {str(k): str(v) for k, v in stored.items()}

    def _pseudonymize_locations(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Replace readable camera labels with their stable pseudonyms for transport.

        queue.jsonl, the in-memory ring buffer and the downloaded report keep the label; only the
        batch handed to the endpoint is rewritten, and the map stays on this machine.

        Args:
            events: Events about to be sent.

        Returns:
            list[dict[str, Any]]: Copies of the events with props.location aliased.
        """
        found: dict[str, str] = {}
        outbound: list[dict[str, Any]] = []
        for event in events:
            props = event.get('props') if isinstance(event.get('props'), dict) else None
            label = str((props or {}).get('location') or '').strip()
            if not label:
                outbound.append(event)
                continue
            alias = _location_alias(label)
            found[alias] = label
            rewritten = dict(event)
            rewritten['props'] = {**props, 'location': alias}
            outbound.append(rewritten)
        if found:
            self._remember_location_aliases(found)
        return outbound

    def _remember_location_aliases(self, aliases: dict[str, str]) -> None:
        """
        Persist the alias to label map locally, where the operator can reverse it.

        Args:
            aliases: Alias to label pairs carried by this batch.

        Returns:
            None
        """
        path = resolve_project_path(LOCATIONS_FILE) or LOCATIONS_FILE
        with self._lock:
            known = dict(self._location_aliases)
            if all(known.get(alias) == label for alias, label in aliases.items()):
                return
            known.update(aliases)
            if len(known) > MAX_LOCATION_ALIASES:
                known = dict(list(known.items())[-MAX_LOCATION_ALIASES:])
            self._location_aliases = known
            payload = json.dumps(known, ensure_ascii=False, indent=2)
        try:
            ensure_parent_dir(path)
            tmp_path = f'{path}.tmp'
            with open(tmp_path, 'w', encoding='utf-8') as handle:
                handle.write(payload)
            os.replace(tmp_path, path)
        except OSError as exc:
            self._log_local(f'Telemetry location map not saved: {exc}')

    def _build_batch(
            self,
            events: list[dict[str, Any]],
            mode: str,
            wire: bool = True,
    ) -> dict[str, Any]:
        """
        Build a batch of events.
        
        Args:
            events: The events to build the batch from.
            mode: The mode of the batch.
            wire: Whether camera labels become pseudonyms. Anything handed to the endpoint must
                use it; a report the operator downloads locally must not.
            
        Returns:
            dict[str, Any]: The batch of events.
        """
        with self._lock:
            dropped_total = self._dropped
            dropped_window = self._dropped_window

        if wire:
            events = self._pseudonymize_locations(events)

        # Stable across retries of the same events, so the receiver can dedup an at-least-once resend
        fingerprint = '|'.join(sorted(str(event.get('id') or '') for event in events))

        return {
            'schema_version': SCHEMA_VERSION,
            'sent_at': _utc_now_iso(),
            'install_id': self._install_id,
            'app_version': APP_VERSION,
            'mode': mode,
            'system': self._get_system_fingerprint(),
            'events': events,
            'meta': {
                'batch_id': hashlib.sha1(fingerprint.encode('utf-8')).hexdigest()[:16],
                'dropped': dropped_total,
                'dropped_window': dropped_window,
                'uptime_sec': int(time.monotonic() - self._started_at),
            },
        }

    def _spill_events(self, events: list[dict[str, Any]]) -> None:
        """
        Spill events to a file for a later replay pass.
        
        Args:
            events: The events to spill.
            
        Returns:
            None
        """
        if not events:
            return
        path = resolve_project_path(QUEUE_FILE) or QUEUE_FILE
        try:
            with self._lock:
                ensure_parent_dir(path)
                if os.path.exists(path) and os.path.getsize(path) > MAX_QUEUE_DISK_BYTES:
                    # Retain the most recent events (FIFO eviction of the oldest ones)
                    evicted = self._trim_jsonl(path)
                    if evicted:
                        self._bump_dropped(evicted)
                        self._log_local(f'Telemetry queue overflow, dropped {evicted} spilled event(s)')
                with open(path, 'a', encoding='utf-8') as handle:
                    for event in events:
                        handle.write(_write_spill_record(1, event) + '\n')
        except OSError as exc:
            # The events are gone with this write; say so instead of losing them silently
            if hasattr(self, 'capture_spill_failure'):
                self.capture_spill_failure(exc)
            self._bump_dropped(len(events))

    def _write_spill_records(self, records: list[tuple[int, dict[str, Any]]], seen_ids: Optional[set[str]] = None) -> None:
        """
        Replace the replay queue file with the given records.

        Args:
            records: Attempt counters and events still waiting for delivery.
            seen_ids: Event ids read at the start of the pass. Lines outside this set were
                appended while a batch was in flight and must not be dropped by the rewrite.

        Returns:
            None
        """
        path = resolve_project_path(QUEUE_FILE) or QUEUE_FILE
        try:
            with self._lock:
                ensure_parent_dir(path)
                merged = list(records)
                if seen_ids is not None and os.path.isfile(path):
                    with open(path, 'r', encoding='utf-8') as handle:
                        raw_lines = handle.readlines()
                    for line in raw_lines:
                        _attempts, event = _read_spill_record(line.strip())
                        if event is None:
                            continue
                        if str(event.get('id') or '') not in seen_ids:
                            merged.append((_attempts, event))
                tmp_path = f"{path}.tmp"
                with open(tmp_path, 'w', encoding='utf-8') as handle:
                    for attempts, event in merged:
                        handle.write(_write_spill_record(attempts, event) + '\n')
                os.replace(tmp_path, path)
        except OSError:
            pass

    def _quarantine_records(self, records: list[tuple[int, dict[str, Any]]]) -> None:
        """
        Park batches the endpoint permanently rejects, out of the replay queue.

        Args:
            records: Attempt counters and events to keep for operator inspection.

        Returns:
            None
        """
        if not records:
            return
        path = resolve_project_path(QUARANTINE_FILE) or QUARANTINE_FILE
        try:
            with self._lock:
                ensure_parent_dir(path)
                with open(path, 'a', encoding='utf-8') as handle:
                    for attempts, event in records:
                        handle.write(_write_spill_record(attempts, event) + '\n')
                self._trim_jsonl(path, max_lines=MAX_QUARANTINE_LINES)
            self._bump_dropped(len(records))
        except OSError:
            pass

    def _trim_jsonl(self, path: str, max_lines: Optional[int] = None) -> int:
        """
        Trim a JSONL file to its most recent entries. The caller must hold self._lock.

        Args:
            path: File to trim.
            max_lines: Keep at most this many trailing lines, or a share of them when omitted.

        Returns:
            int: How many lines were evicted.
        """
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as handle:
                lines = handle.readlines()
        except OSError:
            return 0

        if max_lines is not None:
            keep = lines[-max_lines:] if max_lines > 0 else []
        else:
            keep_count = int(len(lines) * SPILL_KEEP_RATIO)
            keep = lines[-keep_count:] if keep_count > 0 else []

        evicted = len(lines) - len(keep)
        if evicted <= 0:
            return 0
        try:
            tmp_path = f"{path}.tmp"
            with open(tmp_path, 'w', encoding='utf-8') as handle:
                handle.writelines(keep)
            os.replace(tmp_path, path)
        except OSError:
            return 0
        return evicted
