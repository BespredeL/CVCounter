# CVCounter Telemetry API

Client module in CVCounterWEB sends anonymized diagnostics to your HTTP endpoint. No third-party analytics SDKs are used.

Default client endpoint: `https://bespredel.name/api/cvcounter/telemetry`

Automatic sending is **off** by default (`telemetry.enabled: false`). Manual send and JSON download are always available on `/system_info` (HTTP Basic Auth).

## Request

- **Method:** `POST`
- **URL:** value of `telemetry.endpoint`
- **Body:** JSON (UTF-8), batch payload below
- **Headers:**
  - `Content-Type: application/json`
  - `User-Agent: CVCounter/{app_version}`
  - `X-CVCounter-App-Version: {app_version}`
  - `X-CVCounter-Install-Id: {install_id}`
  - `X-CVCounter-Signature: sha256={hex}` — only when `telemetry.hmac_secret` is non-empty (HMAC-SHA256 of the raw body)

## Batch payload schema

```json
{
  "schema_version": 1,
  "sent_at": "2026-07-26T06:00:00Z",
  "install_id": "uuid",
  "app_version": "1.0.0",
  "mode": "auto|manual",
  "system": {
    "python_version": "3.11.x",
    "platform": "...",
    "system": "Windows",
    "release": "...",
    "machine": "AMD64",
    "processor": "...",
    "cpu_count": 8,
    "app_version": "1.0.0",
    "py_torch_version": "...",
    "py_torch_cuda_available": true,
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
      "name": "app_started|counter_started|stream_lost|uncaught_exception|...",
      "props": {},
      "error": {
        "type": "ValueError",
        "message": "...",
        "stack": "..."
      }
    }
  ],
  "meta": {
    "dropped": 0,
    "uptime_sec": 3600
  }
}
```

### Event names (client)

| Name | Type | When |
|------|------|------|
| `app_started` | usage | Application factory finished |
| `app_stopped` | usage | Shutdown signal |
| `counter_started` | usage | Counter started |
| `counter_stopped` | usage | Counter stopped |
| `counter_reset` | usage | Full counter reset |
| `settings_saved` | usage | Settings saved |
| `report_created` | usage | Count/report saved |
| `stream_lost` | usage | Camera frame/reconnect failure (rate-limited) |
| `stream_reconnected` | usage | Camera restored (rate-limited) |
| `uncaught_exception` | error | Logged exception / Flask 500 |

## Expected responses

| Status | Client behavior |
|--------|-----------------|
| `200`-`299` (prefer `{"ok": true}`) | Success; batch discarded |
| `400` / `401` / `413` | Treat as failure; may spill to local `queue.jsonl` |
| `429` / `5xx` / network error | Failure; short timeout; backoff via next flush interval; spill optional |

Client timeout defaults to `telemetry.timeout_sec` (5 seconds). Failed auto batches may append to `storage/telemetry/queue.jsonl` (capped size). Telemetry never raises into the detection loop.

## Privacy (client guarantees)

Never sent:

- RTSP / camera URLs
- Video frames / recordings
- Full `config.json`
- User password hashes
- `secret_key` / HMAC secret values in event bodies

Messages and stacks are sanitized (URLs, credential-like substrings, path hints redacted).

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
  "enabled": false,
  "endpoint": "https://bespredel.name/api/cvcounter/telemetry",
  "send_errors": true,
  "send_usage": true,
  "flush_interval_sec": 300,
  "max_batch_size": 50,
  "max_queue_size": 200,
  "max_stack_chars": 8000,
  "error_dedup_sec": 120,
  "timeout_sec": 5,
  "hmac_secret": ""
}
```

`install_id` is stored in `storage/telemetry/install_id`, not in config.
