# CVCounterWEB — REST API v1 Documentation

CVCounterWEB provides a secure, versioned HTTP REST API under the `/api/v1/` prefix for headless integration, remote automation, robotics, CRM, ERP, and external monitoring systems.

---

## 1. Authentication & Security

All requests to `/api/v1/*` require an active API key passed in either of the following HTTP headers:

```http
X-API-Key: cvc_adm_example1234567890abcdef
```
*or*
```http
Authorization: Bearer cvc_adm_example1234567890abcdef
```

### Access Roles & Permissions

API keys can have one of three hierarchical roles:

| Role | Hierarchy | Allowed Operations |
|---|---|---|
| `read` | Level 1 | Read counter metrics, inspect active locations, download JPEG camera snapshots, query reports, view system health. |
| `write` | Level 2 | All `read` capabilities + control counter states (`start`, `stop`, `pause`, `reset`, `save` counts). |
| `admin` | Level 3 | All `write` capabilities + delete saved reports and manage API keys. |

API keys can be generated, viewed (masked), and revoked at any time via the **Settings -> API** panel in the web interface, or directly in `config/config.json`.

---

## 2. Standard Response Format

All JSON endpoints return a consistent envelope structure:

### Success Response (`200 OK`)
```json
{
  "success": true,
  "data": { ... }
}
```

### Error Response (`4xx` / `5xx`)
```json
{
  "success": false,
  "error": {
    "code": "unauthorized",
    "message": "Missing API key. Provide via 'X-API-Key' or 'Authorization: Bearer <key>'"
  }
}
```

Common error codes:
- `unauthorized` (`401`): Missing, invalid, or disabled API key.
- `forbidden` (`403`): The API key does not have the required permission level for this action.
- `not_found` (`404`): The requested counter, report, or resource does not exist.
- `bad_request` (`400`): Missing parameters or invalid operation.
- `internal_server_error` (`500`): Unexpected server failure.

---

## 3. Endpoints

### 3.1 System (`/api/v1/system`)

#### Check System Health
- **Method:** `GET`
- **Path:** `/api/v1/system/health`
- **Required Role:** `read`
- **Description:** Returns health status of database, active counter threads, and server uptime.

**Example Request:**
```bash
curl -H "X-API-Key: YOUR_API_KEY" http://127.0.0.1/api/v1/system/health
```

**Example Response:**
```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "database": "connected",
    "active_counters_count": 1,
    "total_counters_count": 2,
    "uptime_seconds": 3600
  }
}
```

---

#### System & Hardware Info
- **Method:** `GET`
- **Path:** `/api/v1/system/info`
- **Required Role:** `read`
- **Description:** Returns hardware specs, GPU/CUDA details, and PyTorch runtime versions.

**Example Request:**
```bash
curl -H "X-API-Key: YOUR_API_KEY" http://127.0.0.1/api/v1/system/info
```

---

### 3.2 Counters (`/api/v1/counters`)

#### List All Counters
- **Method:** `GET`
- **Path:** `/api/v1/counters`
- **Required Role:** `read`
- **Description:** Lists all configured detection locations, runtime statuses (`running`, `paused`, `collection`, `stopped`), and live metrics.

**Example Request:**
```bash
curl -H "X-API-Key: YOUR_API_KEY" http://127.0.0.1/api/v1/counters
```

**Example Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": "cam_entrance",
      "name": "Main Entrance",
      "status": "running",
      "video_source": "rtsp://admin:••••••••@192.168.1.100:554/stream",
      "weights": "config/ultralytics/models/yolov8n.pt",
      "counts": {
        "total": 142,
        "current": 142,
        "defect": 0,
        "correct": 0,
        "pending_defect": 0,
        "pending_correct": 0,
        "by_class": [
          {"class_id": 0, "name": "person", "total": 142, "current": 142}
        ]
      }
    }
  ]
}
```

---

#### Get Single Counter Detail
- **Method:** `GET`
- **Path:** `/api/v1/counters/{location}`
- **Required Role:** `read`
- **Description:** Detailed status, counting areas, and performance metrics for a specific counter.

**Example Request:**
```bash
curl -H "X-API-Key: YOUR_API_KEY" http://127.0.0.1/api/v1/counters/cam_entrance
```

---

#### Start Counter
- **Method:** `POST`
- **Path:** `/api/v1/counters/{location}/start`
- **Required Role:** `write`
- **Description:** Starts video capture, tracking, and YOLO inference for the location.

**Example Request:**
```bash
curl -X POST -H "X-API-Key: YOUR_API_KEY" http://127.0.0.1/api/v1/counters/cam_entrance/start
```

---

#### Pause / Resume Counter
- **Method:** `POST`
- **Path:** `/api/v1/counters/{location}/pause`
- **Required Role:** `write`
- **Payload (Optional):**
  ```json
  {"action": "pause"}
  ```
  *(Pass `"pause"`, `"resume"`, or omit to toggle state)*

**Example Request:**
```bash
curl -X POST \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action": "pause"}' \
  http://127.0.0.1/api/v1/counters/cam_entrance/pause
```

---

#### Reset Counter
- **Method:** `POST`
- **Path:** `/api/v1/counters/{location}/reset`
- **Required Role:** `write`
- **Description:** Resets total and class counts to 0 for a running counter.

**Example Request:**
```bash
curl -X POST -H "X-API-Key: YOUR_API_KEY" http://127.0.0.1/api/v1/counters/cam_entrance/reset
```

---

#### Save Report
- **Method:** `POST`
- **Path:** `/api/v1/counters/{location}/save`
- **Required Role:** `write`
- **Description:** Commits current counts to a saved database report.
- **Payload (Optional):**
  ```json
  {
    "correct_count": 0,
    "defect_count": 0,
    "custom_fields": {
      "shift": "Morning",
      "operator": "John Doe"
    }
  }
  ```

**Example Request:**
```bash
curl -X POST \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"defect_count": 2, "custom_fields": {"operator": "Alex"}}' \
  http://127.0.0.1/api/v1/counters/cam_entrance/save
```

---

#### Stop Counter
- **Method:** `POST`
- **Path:** `/api/v1/counters/{location}/stop`
- **Required Role:** `write`
- **Description:** Stops background video stream and frees GPU/CPU resources.

**Example Request:**
```bash
curl -X POST -H "X-API-Key: YOUR_API_KEY" http://127.0.0.1/api/v1/counters/cam_entrance/stop
```

---

#### Capture Snapshot
- **Method:** `GET`
- **Path:** `/api/v1/counters/{location}/snapshot`
- **Required Role:** `read`
- **Query Parameters:**
  - `annotated`: `true` or `false` (default: `false`). When `true` and the counter is running, returns frame with detected bounding boxes and tracking polygons.
- **Response:** Raw binary image with `Content-Type: image/jpeg`.

**Example Request:**
```bash
curl -H "X-API-Key: YOUR_API_KEY" \
  http://127.0.0.1/api/v1/counters/cam_entrance/snapshot?annotated=true \
  --output snapshot.jpg
```

---

### 3.3 Reports (`/api/v1/reports`)

#### List Reports
- **Method:** `GET`
- **Path:** `/api/v1/reports`
- **Required Role:** `read`
- **Query Parameters:**
  - `location`: filter by camera location (optional)
  - `active`: filter by active state (`true` or `false`, optional)
  - `limit`: items per page (default: `20`, max: `100`)
  - `offset`: page offset (default: `0`)

**Example Request:**
```bash
curl -H "X-API-Key: YOUR_API_KEY" "http://127.0.0.1/api/v1/reports?limit=10&location=cam_entrance"
```

**Example Response:**
```json
{
  "success": true,
  "data": {
    "total": 42,
    "limit": 10,
    "offset": 0,
    "items": [
      {
        "id": 15,
        "location": "cam_entrance",
        "total_count": 250,
        "source_count": 250,
        "defects_count": 4,
        "correct_count": 0,
        "custom_fields": {"operator": "Alex"},
        "class_counts": [
          {"class_id": 0, "name": "person", "total": 250}
        ],
        "active": false,
        "created_at": "2026-10-20T08:00:00",
        "updated_at": "2026-10-20T08:30:00"
      }
    ]
  }
}
```

---

#### Get Report Details
- **Method:** `GET`
- **Path:** `/api/v1/reports/{report_id}`
- **Required Role:** `read`

**Example Request:**
```bash
curl -H "X-API-Key: YOUR_API_KEY" http://127.0.0.1/api/v1/reports/15
```

---

#### Delete Report
- **Method:** `DELETE`
- **Path:** `/api/v1/reports/{report_id}`
- **Required Role:** `admin`
- **Description:** Permanently deletes a saved count session from the database.

**Example Request:**
```bash
curl -X DELETE -H "X-API-Key: YOUR_API_KEY" http://127.0.0.1/api/v1/reports/15
```
