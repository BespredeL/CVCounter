# CVCounter Wiki

Welcome to the documentation for the **CVCounter** project!

# Project Description

CVCounter is a web-based system for detecting, tracking, and counting objects in video streams. It serves as a simple and convenient tool for monitoring object flows (e.g., entry and exit or conveyor systems).

This solution does not require additional client-side software and works on any device with a browser. The project is lightweight and resource-efficient, especially when the video mode is not used.

### Key Features

- Web dashboard with counter cards, search, status filters, and camera previews
- Real-time count updates via Socket.IO
- Video view with recognition results (MJPEG stream)
- Text-only modes for simplicity and resource-saving
- Multi-counter display for monitoring N locations simultaneously (e.g., entry and exit)
- Visual counting area (polygon zone) editor
- Per-counter settings modal on the dashboard
- Reports on saved counts
- System information page (GPU/CUDA/PyTorch)
- Modular architecture with pluggable detection backends
- SORT multi-object tracking and polygon zone counting
- Support for RTSP streams, USB cameras, and video files

### Architecture

The application uses a Flask factory pattern (`app.py`) with blueprints:

| Blueprint | Module | Purpose |
|-----------|--------|---------|
| `main` | `routes/main.py` | Dashboard, static pages |
| `counters` | `routes/counters.py` | Counter UI, API, MJPEG stream |
| `reports` | `routes/reports.py` | Saved count reports |
| `settings` | `routes/settings.py` | Global config editor (auth required) |

---

## Installation

### Method 1: Manual Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/BespredeL/CVCounter.git
   ```
2. **Navigate to the project directory:**
   ```bash
   cd CVCounter
   ```
3. **Create a virtual environment:**
   ```bash
   python3 -m venv venv
   ```
4. **Activate the virtual environment:**
   - On Windows:
     ```bash
     .\venv\Scripts\activate
     ```
   - On Linux/Mac:
     ```bash
     source venv/bin/activate
     ```
5. **Install dependencies:**
   ```bash
   pip3 install -r requirements.txt
   ```
   > **Note:** PyTorch is not included in `requirements.txt` and must be installed separately for GPU support. See comments in `requirements.txt` for CUDA/TensorRT instructions. Docker images include PyTorch pre-installed.
6. **Copy the configuration file:**
   ```bash
   mv config/config.example.json config/config.json
   ```
   On Windows:
   ```bash
   copy config\config.example.json config\config.json
   ```
7. **Edit `config/config.json`:** set video sources, model paths, and `model_type` for each detection.
8. **Run the application:**
   ```bash
   python app.py
   ```
   Default URL: `http://127.0.0.1:8080`

### Method 2: Docker Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/BespredeL/CVCounter.git
   ```
2. **Navigate to the project directory:**
   ```bash
   cd CVCounter
   ```
3. **Build and run using Docker Compose:**
   ```bash
   docker-compose up --build
   ```

---

# Detection Backends

Detectors are registered via a plugin registry (`system/object_detection/registry.py`). Set `model_type` in the configuration.

| `model_type` | Backend | Model formats |
|--------------|---------|---------------|
| `yolo` | [Ultralytics YOLO](https://github.com/ultralytics/ultralytics) | `.pt` |
| `opencv`, `opencv_dnn` | [OpenCV DNN](https://docs.opencv.org) | `.onnx`, `.pb`, Darknet (`.weights` + `.cfg`) |
| `onnx`, `onnxruntime` | [ONNX Runtime](https://onnxruntime.ai/) | `.onnx` (YOLO export) |

### Configuration Examples

**Ultralytics YOLO (default):**
```json
"model_type": "yolo",
"weights_path": "config/ultralytics/models/yolov8n.pt",
"device": 0
```

**OpenCV DNN + ONNX:**
```json
"model_type": "opencv",
"weights_path": "config/opencv/models/yolov8n.onnx",
"input_size": 640,
"backend": "CUDA",
"target": "CUDA"
```

**Darknet via OpenCV:**
```json
"model_type": "opencv_dnn",
"weights_path": "config/opencv_dnn/models/yolov4.weights",
"model_config_path": "config/opencv_dnn/models/yolov4.cfg",
"input_size": 416
```

**ONNX Runtime:**
```json
"model_type": "onnx",
"weights_path": "config/onnx/models/yolov8n.onnx",
"input_size": 640,
"providers": ["CUDAExecutionProvider", "CPUExecutionProvider"]
```

### Additional Detection Parameters

| Parameter | Applies to | Description |
|-----------|------------|-------------|
| `weights_path` | all | Path to model file |
| `model_config_path` | OpenCV Darknet | Path to `.cfg` file |
| `input_size` | OpenCV, ONNX | Input size: number or `[width, height]`, default `640` |
| `backend` | OpenCV | `OPENCV`, `CUDA`, `DEFAULT`, etc. |
| `target` | OpenCV | `CPU`, `CUDA`, `CUDA_FP16`, etc. |
| `providers` | ONNX | List of ONNX Runtime providers |
| `confidence`, `iou` | all | Detection thresholds |
| `device` | YOLO, ONNX | Compute device (`0`, `cpu`, etc.) |
| `vid_stride` | YOLO | Frame stride during inference |
| `classes` | all | Class filter, e.g. `{ "0": "person" }` |

### Export YOLO to ONNX

```bash
yolo export model=config/ultralytics/models/yolov8n.pt format=onnx
```

### Training

Use `train.py` for training and exporting YOLO models (separate from the web application).

### Adding a Custom Detector

1. Create a class inheriting `BaseObjectDetectionService` and decorate it with `@register('my_detector')`.
2. Import the module in `system/object_detection/__init__.py`.
3. Set `"model_type": "my_detector"` in the configuration.

---

# Configuration

**All primary configurations are stored in `config/config.json`** (copy from `config/config.example.json`).

## General Parameters `general`

| Parameter | Description | Default Value |
|-----------|-------------|---------------|
| `debug` | Enable debug mode | `true` |
| `system_check` | Print GPU/CUDA/PyTorch info on startup | `true` |
| `log_path` | Path to the log file | `storage/logs/cvcounter.log` |
| `log_level` | Minimum log level | `INFO` |
| `log_console` | Enable logging to console | `false` |
| `default_language` | Default language (`ru`, `en`) | `ru` |
| `allow_unsafe_werkzeug` | Allow unsafe operations in Werkzeug | `false` |
| `button_change_theme` | Show theme change button | `true` |
| `button_fullscreen` | Show fullscreen button | `true` |
| `button_backward` | Show back button | `false` |
| `button_save_capture` | Show save capture button | `false` |
| `collapsed_keyboard` | Show on-screen keyboards collapsed | `true` |

## Server Parameters `server`

| Parameter | Description | Default Value |
|-----------|-------------|---------------|
| `host` | Server address | `0.0.0.0` |
| `port` | Server port | `8080` |
| `use_reloader` | Enable reload mode | `false` |
| `log_output` | Enable log output | `false` |
| `secret_key` | Flask secret key (auto-generated if empty) | `""` |
| `allowed_origins` | Allowed address for Access-Control-Allow-Origin | `*` |
| `socketio_async_mode` | Socket.IO async mode | `threading` |
| `socketio_transports` | Socket.IO transport list | `["polling", "websocket"]` |
| `socketio_upgrade` | Allow transport upgrade | `true` |

## User Parameters `users`

| Parameter | Description | Default Value |
|-----------|-------------|---------------|
| `admin` | Username → password hash (scrypt) | scrypt hash (default password: `admin`) |

> Passwords are stored as scrypt hashes, not plaintext. Default credentials: `admin` / `admin`.

## Database `db`

| Parameter | Description | Default Value |
|-----------|-------------|---------------|
| `uri` | Database connection URI | `sqlite:///system/db/database.sqlite` |
| `prefix` | Table prefix | `""` |

## Form Parameters `form`

| Parameter | Description | Default Value |
|-----------|-------------|---------------|
| `defect_show` | Show defect form | `true` |
| `correct_show` | Show correction form | `true` |
| `custom_fields` | Custom field definitions (object) | see `config.example.json` |

`custom_fields` is an object where each key is a field ID. Supported types: `text`, `date`, `datetime-local`, `textarea`, `select` (with `options` array).

## Default Detection Configuration `detection_default`

| Parameter | Description | Default Value |
|-----------|-------------|---------------|
| `model_type` | Model type | `yolo` |
| `weights_path` | Model path | `config/ultralytics/models/yolov8n.pt` |
| `confidence` | Confidence threshold | `0.7` |
| `iou` | IOU threshold | `0.7` |
| `device` | Compute device | `0` |
| `vid_stride` | Video stream step | `1` |
| `indicator_size` | Indicator size | `10` |
| `video_show_scale` | Video display scale on the page (%) | `70` |
| `video_show_quality` | Video display quality on the page (%) | `50` |
| `video_fps` | Manual FPS setting (0 = automatic) | `0` |
| `video_reconnect_attempts` | Max camera connection attempts on start and after stream loss; counter stops when exhausted | `5` |
| `counting_area` | Counting area (polygon) | `[[0,0],[100,0],[100,100],[0,100]]` |
| `counting_area_color` | Counting area color (BGR) | `[67, 211, 255]` |
| `classes` | Detection classes filter | `{}` |

## Default Video Recording `detection_default`.`recording`

| Parameter | Description | Default Value |
|-----------|-------------|---------------|
| `enable` | Enable recording | `false` |
| `path` | Video saving path | `storage/saved_recordings` |
| `scale` | Video size (in percent) | `50` |
| `quality` | Video quality | `70` |

## Detection Configurations `detections`.`ExampleCam`

Each key in `detections` is a counter `location` (Latin characters, used in URLs).

| Parameter | Description | Default Value |
|-----------|-------------|---------------|
| `label` | Counter display label | `Label ExampleCam` |
| `start_total_count` | Initial counter value | `0` |
| `video_path` | Path to video file or camera source | `""` |
| `model_type` | Model type | `yolo` |
| `weights_path` | Model path | `config/ultralytics/models/yolov8n.pt` |
| `confidence` | Confidence threshold | `0.7` |
| `iou` | IOU threshold | `0.7` |
| `device` | Compute device | `0` |
| `vid_stride` | Video stream step | `1` |
| `indicator_size` | Indicator size | `10` |
| `video_show_scale` | Video display scale (%) | `70` |
| `video_show_quality` | Video display quality (%) | `30` |
| `video_fps` | Manual FPS (0 = automatic) | `0` |
| `video_reconnect_attempts` | Max connection attempts (inherits from `detection_default` if omitted) | `5` |
| `counting_area` | Counting area (polygon) | `[[0,0],[100,0],[100,100],[0,100]]` |
| `counting_area_color` | Counting area color (BGR) | `[255, 64, 0]` |
| `classes` | Detection classes filter | `{}` |
| `dataset_create.enable` | Enable dataset creation | `true` |
| `dataset_create.probability` | Probability of image saving (0.01–1) | `0.05` |
| `dataset_create.path` | Path for saving dataset images | `storage/saved_images/ExampleCam` |
| `recording.enable` | Enable recording | `true` |
| `recording.path` | Video save path (inherits from `detection_default` if omitted) | `storage/saved_recordings` |
| `recording.scale` | Video size (in percent) | `80` |
| `recording.quality` | Video quality | `60` |

---

# Interface

Default base URL: `http://127.0.0.1:8080`

## Dashboard

The home page displays counter cards with status badges (running/paused/stopped), search, status filters, camera preview thumbnails, and transport controls (start/pause/stop).

**URL:**
```
http://127.0.0.1:8080/
```

## Main View (Video)

Displays the video feed with counters showing detected objects. Primary interface for real-time monitoring.

**URL:**
```
http://127.0.0.1:8080/counter/{location}
```
or
```
http://127.0.0.1:8080/counter/{location}/video
```

## Text View

Shows only counter values without video. Suitable for low-resource devices.

**URL:**
```
http://127.0.0.1:8080/counter/{location}/text
```

## Multi-Counter View

Displays N counters simultaneously on one fullscreen page. Replaces the legacy dual-counter view. Each card shows the current batch and total immediately on load (from live counter state or the last DB record), then updates via Socket.IO.

**URL:**
```
http://127.0.0.1:8080/counter_multi/text?locations=Cam1,Cam2
```

> **Legacy:** `/counter_dual/text/{location_first}/{location_second}` redirects to the multi-counter view.

## Counting Area Editor

Visual polygon editor for the counting zone. Uses a snapshot from the live stream as background.

**URL:**
```
http://127.0.0.1:8080/counter/{location}/counting_area
```

## Reports

View saved count records with pagination.

**URL:**
```
http://127.0.0.1:8080/reports
http://127.0.0.1:8080/reports/{location}
http://127.0.0.1:8080/reports/{location}/{report_id}
```

## Settings and System Info

Global configuration editor and GPU/system information. **Requires HTTP Basic Auth.**

**URL:**
```
http://127.0.0.1:8080/settings
http://127.0.0.1:8080/system_info
```

## Help

In-app help page.

**URL:**
```
http://127.0.0.1:8080/page/help
```

---

# API Endpoints

Counter control and data endpoints (no auth required unless noted):

| Method | Path | Description |
|--------|------|-------------|
| GET | `/counter/{location}/bootstrap` | Start counter thread in background |
| GET | `/start_count/{location}` | Resume counting |
| GET | `/pause_count/{location}` | Pause counting |
| GET | `/stop_count/{location}` | Stop thread and cleanup |
| POST | `/save_count/{location}` | Persist count and custom fields to DB |
| GET | `/reset_count/{location}` | Reset total count |
| POST | `/reset_count_current/{location}` | Reset current session count |
| GET | `/save_capture/{location}` | Save current frame snapshot |
| GET | `/counter_get_frames/{location}` | MJPEG video stream |
| GET | `/counter/{location}/preview` | Dashboard thumbnail JPEG |
| GET | `/counter/{location}/settings/form` | HTML partial for settings modal |
| POST | `/counter/{location}/settings` | Save per-counter detection settings |
| GET | `/counter/{location}/counting_area/data` | JSON: current polygon and color |
| GET | `/counter/{location}/counting_area/snapshot` | Single JPEG frame for editor |
| POST | `/counter/{location}/counting_area` | Save polygon (JSON body) |
| POST | `/settings_save` | Save global config (**auth required**) |

---

# Authentication

The application uses **HTTP Basic Auth** (Flask-HTTPAuth). Passwords are stored as scrypt hashes in `config/config.json` under `users`.

**Protected routes:**
- `/settings`
- `/settings_save`
- `/system_info`

**Public routes:** counter pages, reports, dashboard, and all counter API endpoints.

---

# Real-time (Socket.IO)

The server emits events to connected clients (no client-to-server handlers):

| Event | Source | Payload |
|-------|--------|---------|
| `{location}_count` | ObjectCounter | `{total, current, ...}` |
| `{location}_notification` | NotificationManager | `{type, message}` |
| `counter_status_event` | NotificationManager | `{data: {status, location}}` |

Counter statuses: `started`, `paused`, `stopped`, `error`.

Socket.IO transport is configured via `server.socketio_async_mode`, `server.socketio_transports`, and `server.socketio_upgrade` in the config.

---

# Contributing to the Project

Contributions to the project are always welcome! To make changes, follow these steps:

- Fork this repository.
- Create a new branch.
  ```bash
  git checkout -b feature/your-feature
  ```
- Make your changes and commit them.
  ```bash
  git commit -m "Added a new feature"
  ```
- Push your changes.
  ```bash
  git push origin feature/your-feature
  ```
- Submit a PR (Pull Request) for review.

Before submitting, ensure your changes do not disrupt existing functionality.

---

# Frequently Asked Questions (FAQ)

### 1. What are the minimum system requirements for the server?

- **Processor:** Modern 4-core processor (e.g., Intel Core i5 or AMD Ryzen 5).
- **RAM:** At least 8 GB (16 GB or more is recommended for stable video stream processing).
- **Storage:** SSD for storing datasets and logs.
- **GPU:** A GPU significantly speeds up processing and reduces system load. Minimum GPU requirements:
  - **NVIDIA GTX 1050 (2 GB VRAM):** Suitable for low-frame-rate image processing.
  - **NVIDIA GTX 1660 (6 GB VRAM):** Recommended for real-time video streams and high-resolution videos (up to 720p).
  - **NVIDIA RTX 2060 or higher (6 GB+ VRAM):** Stable performance for YOLO models in real-time at resolutions of 1080p and above.

> **Note:** YOLO supports computation on NVIDIA GPUs using CUDA. GPUs from other manufacturers (e.g., AMD) may work but require additional configuration and may have lower performance.

### 2. What are the minimum system requirements for the client?

Any device with a web browser capable of running JavaScript.

### 3. How do I add a new camera/counter?

Add a new entry under `detections` in `config/config.json`. The key becomes the `location` used in URLs (use Latin characters). Restart the application or use the dashboard to bootstrap the counter.

### 4. How do I display multiple counters on one screen?

Use the multi-counter view:
```
http://127.0.0.1:8080/counter_multi/text?locations=Cam1,Cam2,Cam3
```
You can also select multiple counters on the dashboard and open them together.

### 5. What should I do if the video does not display?

Check the camera's functionality and ensure it is correctly connected. Verify `video_path` in the configuration. If the camera is unreachable, the counter retries up to `video_reconnect_attempts` times (default `5`, set in `detection_default` or per counter) and then stops with an error status. Check logs at `storage/logs/cvcounter.log`.

### 6. What should I do if Socket.IO does not connect?

Check `server.socketio_async_mode` (use `threading` with Werkzeug), `server.socketio_transports` (include `polling` for compatibility), and `server.allowed_origins`.

### 7. Where are the logs stored?

Default log path: `storage/logs/cvcounter.log` (configurable via `general.log_path`).

### 8. How do I prevent the counting interface from being closed?

You can run the browser in kiosk mode to prevent users from exiting it. For example, with Google Chrome, use the `--kiosk --start-fullscreen` options.

---

# License

The project is distributed under the AGPL-3.0 license. Details can be found in the [LICENSE](https://github.com/BespredeL/CVCounter/blob/master/LICENSE) file.
