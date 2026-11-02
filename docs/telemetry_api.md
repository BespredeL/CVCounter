# CVCounter Telemetry API

Client module in CVCounter sends pseudonymized diagnostics to your HTTP endpoint: camera labels travel as stable aliases, not as the names you typed in settings. No third-party analytics SDKs are used.

Default client endpoint: `https://bespredel.name/api/cvcounter/telemetry`

Automatic sending is **on** by default (`telemetry.enabled: true`). You can disable it at any time in settings or `config.json`. Manual send and JSON download are always available on `/system_info` (session login required when `users` is configured).

## Request

- **Method:** `POST`
- **URL:** value of `telemetry.endpoint`
- **Body:** JSON (UTF-8), batch payload below
- **Headers:**
  - `Content-Type: application/json`
  - `Content-Encoding: gzip` (optional, when `telemetry.compress` is true)
  - `User-Agent: CVCounter/{app_version}`
  - `X-CVCounter-App-Version: {app_version}`
  - `X-CVCounter-Install-Id: {install_id}`
  - `X-CVCounter-Batch-Id: {hex}` - same value for every retry of the same event set
  - `X-CVCounter-Signature: sha256={hex}` - only when `telemetry.hmac_secret` is non-empty (HMAC-SHA256 of the raw body)

## Batch payload schema

```json
{
  "schema_version": 1,
  "sent_at": "2026-07-26T06:00:00Z",
  "install_id": "uuid",
  "app_version": "5.9.0",
  "mode": "auto|manual|replay",
  "system": {
    "python_version": "3.11.x",
    "platform": "...",
    "system": "Windows",
    "release": "...",
    "machine": "AMD64",
    "processor": "...",
    "cpu_count": 8,
    "app_version": "5.9.0",
    "py_torch_version": "...",
    "py_torch_cuda_available": true,
    "openvino_version": "...",
    "ram_total_mb": 16384,
    "ram_available_mb": 8192,
    "gpu_name": "...",
    "counters_count": 3,
    "counters_running": 1,
    "detector_backends": ["yolo"]
  },
  "events": [
    {
      "id": "uuid",
      "ts": "2026-07-26T06:00:00Z",
      "type": "usage|error",
      "name": "app_started|counter_started|stream_lost|uncaught_exception|logged_error|...",
      "props": {},
      "error": {
        "type": "ValueError",
        "message": "...",
        "stack": "..."
      }
    }
  ],
  "meta": {
    "batch_id": "3f2a9c1d0b4e5a67",
    "dropped": 0,
    "dropped_window": 0,
    "uptime_sec": 3600
  }
}
```

`meta.dropped` counts every event the client discarded since the process started (full in-memory queue, disk rotation, records the endpoint kept rejecting). `meta.dropped_window` is the same counter reset to `0` after the endpoint accepts a batch, so a receiver can tell "this install is losing data now" from "it lost data at some point".

### Event names (client)

| Name | Type | When |
|------|------|------|
| `app_started` | usage | Application factory finished |
| `app_stopped` | usage | Shutdown signal |
| `app_heartbeat` | usage | Periodic 24h keep-alive / uptime signal |
| `counter_started` | usage | Counter started |
| `counter_stopped` | usage | Counter stopped |
| `counter_reset` | usage | Full counter reset |
| `settings_saved` | usage | Settings saved |
| `report_created` | usage | Count/report saved |
| `stream_lost` | usage | Camera frame/reconnect failure (rate-limited) |
| `stream_reconnected` | usage | Camera restored (rate-limited) |
| `stream_performance` | usage | Aggregate FPS and inference latency report |
| `doctor_summary` | usage | Subsystem ids and statuses from the system doctor, on start and every 24 h |
| `delivery_failure` | usage | The endpoint rejected every batch three times in a row |
| `spill_failure` | usage | The backlog could not be written to disk, so events were lost |
| `startup_failed` | usage | `app.py` crashed before or while starting the server |
| `uncaught_exception` | error | Logged exception / Flask 500 / sys.exc_info / a thread that died |
| `logged_error` | error | Unhandled logger.error message |
| `client_javascript_error` | error | Unhandled frontend browser exception or rejection |

## Idempotency

Delivery is **at-least-once**. The client mirrors its in-memory buffer to `queue.jsonl` every 5 minutes (and at process exit), so a batch can be acknowledged, then resent after a restart or a crash between the acknowledgment and the file cleanup. Batches sent from that backlog carry `mode: "replay"`, and they may include events the receiver already has.

Deduplicate on the receiving side:

1. Prefer `events[].id` (UUID per event, stable across retries) as the natural key.
2. `meta.batch_id` / `X-CVCounter-Batch-Id` is derived from the set of event ids in the batch: two batches with the same id carry the same events, so a whole batch can be skipped as a duplicate.
3. Counters, not last-write-wins: telemetry events are facts about a moment, and a resend of the same `events[].id` should not advance any aggregate twice.

## Expected responses

| Status | Client behavior |
|--------|-----------------|
| `200`-`299` (prefer `{"ok": true}`) | Success; batch discarded; backlog in `queue.jsonl` is replayed right away |
| `413` | Failure; the batch is kept and retried in halves until it fits |
| other `4xx` (`400`, `401`, `422`) | Permanent failure; the batch is retried up to 3 times, then parked in `quarantine.jsonl` so it cannot block the backlog |
| `429` / `5xx` / network error | Temporary failure; spill to `queue.jsonl` and hold the next attempt back. `Retry-After` (seconds or HTTP date) is honored when present, otherwise the delay grows 60 → 120 → 240 → 480 → 900 s (±20 %) and resets on the first accepted batch |

Client timeout defaults to `telemetry.timeout_sec` (10 seconds). Failed auto batches append to `storage/telemetry/queue.jsonl` (capped size) and are replayed on the next flush or right after a restart — up to 10 batches of `max_batch_size` events per replay pass. A temporary failure stops the pass with the file untouched; a permanent one moves those records to `storage/telemetry/quarantine.jsonl` (last 200 records) and the pass continues, so one rejected batch never blocks the rest of the backlog. Queue records are written as `{"attempts": N, "event": {...}}`; bare events written by earlier versions are read as `attempts: 1`. The worker thread survives any internal error and is restarted by the next event, at most 3 times a minute. Every attempt is appended to `storage/telemetry/delivery.jsonl` (last 200 records: time, mode, HTTP status, event count, payload size, latency, next retry) and the last five are shown on the System info page, so a receiver outage is visible on the box. Telemetry maintains an in-memory ring buffer of recent events for manual export even when auto-reporting is disabled. Telemetry never raises into the detection loop.

## Privacy (client guarantees)

Never sent:

- RTSP / camera URLs
- Video frames / recordings
- Full `config.json`
- User password hashes
- `secret_key` / HMAC secret values in event bodies

Messages and stacks are sanitized (URLs, credential-like substrings, Windows / POSIX / UNC path hints redacted).

Camera labels are **pseudonymized, not anonymous**. `events[].props.location` leaves the machine as
`sha256(label.strip().casefold())` truncated to 8 hex characters, so the same camera keeps one id across
batches, restarts and versions, and a time series per camera stays possible. The alias to label map is kept
on the box in `storage/telemetry/locations.json`; the queue file, the in-memory ring buffer and the JSON you
download from `/system_info` keep the readable label, so an operator can always tell which alias is which
camera. Anyone with both the payload and that file can reverse it.

## HMAC verification (server example)

```python
import hashlib
import hmac

def verify_signature(body: bytes, secret: str, header_value: str) -> bool:
    if not header_value.startswith('sha256='):
        return False
    expected = hmac.new(secret.encode('utf-8'), body, hashlib.sha256).hexdigest()
    provided = header_value[len('sha256='):]
    return hmac.compare_digest(expected, provided)
```

## Storage recommendations (your site)

- Key installations by `install_id` (opaque UUID from the client).
- Group errors by `error.type` + hash of `error.message`.
- Keep raw stacks short-lived; prefer aggregates for dashboards.
- Reject oversized bodies (`413`).

## Client config (`config.json`)

```json
"telemetry": {
  "enabled": true,
  "endpoint": "https://bespredel.name/api/cvcounter/telemetry",
  "send_errors": true,
  "send_usage": true,
  "flush_interval_sec": 3600,
  "max_batch_size": 200,
  "max_queue_size": 400,
  "max_stack_chars": 8000,
  "error_dedup_sec": 600,
  "timeout_sec": 10,
  "hmac_secret": "",
  "compress": true
}
```

`install_id` is stored in `storage/telemetry/install_id`, not in config.

Numeric keys are clamped to the accepted range; out-of-range values in `config.json` are reported by the settings validator and fall back to the defaults above:
`flush_interval_sec` 1-86400, `max_batch_size` 1-500, `max_queue_size` 1-5000, `max_stack_chars` 1-100000, `error_dedup_sec` 1-86400, `timeout_sec` 1-60.
`max_queue_size` is applied when the worker starts, so changing it needs an application restart (the log says so if a running worker ignores the new value).
