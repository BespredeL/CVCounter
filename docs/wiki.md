# CVCounter — Documentation (Wiki)

[![Website](https://img.shields.io/badge/website-cvcounter.createdby.ru-4dabf7.svg)](https://cvcounter.createdby.ru)
[![Author](https://img.shields.io/badge/author-bespredel.name-8a2be2.svg)](https://bespredel.name)
[![Wiki RU](https://img.shields.io/badge/Wiki-RU-blue.svg)](wiki_ru.md)
[![Wiki EN](https://img.shields.io/badge/Wiki-EN-blue.svg)](wiki.md)
[![License](https://img.shields.io/badge/license-AGPL--3.0-458a7b.svg)](https://github.com/BespredeL/CVCounter/blob/master/LICENSE)

Welcome to the comprehensive technical documentation for **CVCounter**!

---

## 📑 Table of Contents

1. [Overview & Features](#-overview--features)
2. [Application Architecture](#-application-architecture)
3. [Installation & Deployment](#-installation--deployment)
4. [Detection Systems & Inference](#-detection-systems--inference)
5. [Complete Configuration Guide (`config.json`)](#-complete-configuration-guide-configjson)
6. [Web Interface & Operation Modes](#-web-interface--operation-modes)
7. [Datasets, Annotation & Model Training](#-datasets-annotation--model-training)
8. [REST API Reference](#-rest-api-reference)
9. [Authentication & Security](#-authentication--security)
10. [Real-Time Events (Socket.IO)](#-real-time-events-socketio)
11. [Frequently Asked Questions (FAQ)](#-frequently-asked-questions-faq)
12. [Contributing & License](#-contributing--license)

---

## 🧠 Overview & Features

**CVCounter** is a production-grade, scalable computer vision system designed for real-time object detection, tracking, and counting in video streams. Built as a self-hosted Flask web application, it requires no client-side software installations: operators interact with the system via standard web browsers across PCs, tablets, or touch terminals.

### Key Capabilities:

- 🎯 **Multi-Zone Counting:** Interactive visual polygon editor (arbitrary number of zones per counter, custom BGR colors, union mask logic).
- 🔄 **ByteTrack Multi-Object Tracking:** High-accuracy tracker maintaining persistent IDs between frames to prevent double-counting.
- 🏷️ **Per-Class Breakdown:** Real-time counters showing both total counts and current batch counts partitioned by detection classes.
- 🎥 **Flexible Video Inputs:** RTSP/RTMP network camera streams, local webcams (USB/V4L2), and pre-recorded video files.
- 🎬 **Event-Driven Recording:** Video clips start recording automatically upon object detection and stop following a configurable `idle_timeout`.
- 🧠 **Multi-Engine Inference:** Seamless runtime selection between ONNX Runtime, Intel OpenVINO, OpenCV DNN, and Ultralytics YOLO.
- 📚 **Full Dataset Workflow:** In-browser frame capture, bounding box/polygon annotation, active learning, autolabeling, YOLO training, and 1-click model weight deployment.
- 📊 **Reports & Analytics:** Paginated session history, defect and manual correction logs, saved media playback, and A4 print-ready layouts with sign-off blocks.
- 🚀 **1-Click Installer:** Cross-platform scripts (`install.bat` / `install.sh`) automatically detecting GPUs (NVIDIA CUDA, AMD DirectML, Intel Arc / OpenVINO).
- 🛠️ **AI Runtimes Center:** In-app inspection and automated installation of missing inference libraries (CUDA, TensorRT, OpenVINO).
- 🔐 **Security:** Session authentication, administrative protection for settings and datasets, and scrypt password hashing.

---

## 🏛️ Application Architecture

The system is organized into modular blueprints utilizing Flask's Application Factory pattern:

```
CVCounter/
├── app.py                      # Application entrypoint, blueprint & socketio registration
├── train.py                    # Standalone CLI training & export utility for YOLO
├── install.py                  # Cross-platform automated setup script
├── config/                     # Configuration files & model storage
│   ├── config.json             # Active configuration file
│   ├── config.example.json     # Reference default configuration
│   ├── database.sqlite         # SQLite database (sessions, batch history)
│   └── ultralytics/            # Ultralytics YOLO models and configs
├── routes/                     # Blueprint controllers
│   ├── main.py                 # Dashboard, authentication, static pages
│   ├── counters.py             # Counters, MJPEG streaming, zone editor, counting API
│   ├── reports.py              # Reports viewer, saved media, export
│   ├── datasets.py             # Datasets, annotation, training controllers
│   └── settings.py             # Configuration editor, system diagnostics, AI runtimes
├── system/                     # Core system modules
│   ├── core/                   # Tracking and counting logic (ObjectCounter)
│   ├── object_detection/       # Detection backend abstractions and registry
│   ├── managers/               # Video streams, database, notifications, training
│   ├── datasets/               # Annotation storage and dataset services
│   ├── training/               # Model training pipelines and export tools
│   └── utils/                  # I18n, telemetry, input validators, logger
├── static/                     # CSS, JS, fonts, and UI assets
├── templates/                  # Jinja2 templates
└── storage/                    # Logs, saved clips, snapshots, datasets
```

### Core Blueprints:

| Blueprint | Module | URL Prefix | Purpose |
|---|---|---|---|
| `main` | `routes/main.py` | `/` | Dashboard, authentication (`/login`, `/logout`), help (`/page/help`) |
| `counters` | `routes/counters.py` | `/` | Counter screens, MJPEG video, zone editor, batch recording |
| `reports` | `routes/reports.py` | `/reports` | Session histories, captured media viewer, printable A4 layouts |
| `datasets` | `routes/datasets.py` | `/datasets` | Data preparation, image annotation, model training (*auth*) |
| `settings` | `routes/settings.py` | `/settings`, `/system_info` | Configurator, system diagnostics, log terminal, runtimes (*auth*) |

---

## 📦 Installation & Deployment

### Method 1: Automatic 1-Click Installation (Recommended)

The installer script `install.py` inspects your hardware, provisions the appropriate PyTorch and ONNX Runtime packages with hardware acceleration, configures a virtual environment, and creates initial configs:

- **Windows:** Double-click **`install.bat`**. Launch the app with **`start.bat`**.
- **Linux / macOS:**
  ```bash
  chmod +x install.sh start.sh
  ./install.sh
  ./start.sh
  ```

#### Supported Acceleration Profiles:
- **`nvidia_cuda`:** Detects NVIDIA driver versions and installs compatible PyTorch builds (CUDA 12.4 / 12.1 / 11.8) and `onnxruntime-gpu`.
- **`amd_directml`:** DirectX DirectML acceleration (`torch-directml`, `onnxruntime-directml`) on AMD Radeon GPUs in Windows (ROCm in Linux).
- **`intel_openvino`:** Neural network optimization for Intel Core/Xeon CPUs, integrated iGPUs, Intel Arc discrete GPUs, and NPUs.
- **`cpu`:** Universal fallback profile for systems without dedicated graphics.

Installer options:
```bash
python install.py --profile nvidia_cuda  # Force hardware acceleration profile
python install.py --reinstall            # Force package reinstallation
python install.py --no-color             # Disable ANSI colored output
```

---

### Method 2: Manual Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/BespredeL/CVCounter.git
   cd CVCounter
   ```
2. Create and activate a virtual environment:
   ```bash
   # Linux/macOS:
   python3 -m venv venv
   source venv/bin/activate

   # Windows:
   python -m venv venv
   .\venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   
   # Optional: For YOLO training and .pt weights
   pip install -r requirements-ultralytics.txt

   # Optional: For Intel OpenVINO acceleration
   pip install -r requirements-openvino.txt
   ```
4. Prepare configuration:
   ```bash
   cp config/config.example.json config/config.json
   ```
5. Run the application:
   ```bash
   python app.py
   ```
   Open `http://localhost:8080`. Default login credentials: `admin` / `admin`.

---

### Method 3: Docker Deployment

```bash
docker-compose up --build
```
Mounted volumes ensure persistent storage for configuration (`config/`) and media/logs (`storage/`).

---

## 🧠 Detection Systems & Inference

The registry (`system/object_detection/registry.py`) decouples computer vision engines via the unified `BaseObjectDetectionService` interface.

### Supported `model_type` Options:

| `model_type` | Engine | License | Formats | Best Use Case |
|---|---|---|---|---|
| **`auto`** | Auto-selection | — | `.onnx`, `.pt`, `.engine`, `.xml` | **Default.** Selects backend automatically based on model file extension |
| **`onnx`**, `onnxruntime` | [ONNX Runtime](https://onnxruntime.ai/) | MIT | `.onnx` (YOLOv5–v11, RT-DETR) | Maximum cross-platform throughput (CUDA, DirectML, CPU) |
| **`openvino`**, `openvino_dnn` | [Intel OpenVINO](https://www.intel.com/openvino) | Apache-2.0 | `.xml`/`.bin`, `.onnx` | Peak performance on Intel CPUs, Arc GPUs, and integrated iGPUs |
| **`yolo`**, `ultralytics` | [Ultralytics YOLO](https://github.com/ultralytics/ultralytics) | AGPL-3.0 | `.pt`, `.engine` (TensorRT) | Native PyTorch models, TensorRT engines, model training |
| **`opencv`**, `opencv_dnn` | [OpenCV DNN](https://docs.opencv.org) | Apache-2.0 | `.onnx`, Darknet (`.weights` + `.cfg`) | Lightweight operation without heavy PyTorch dependencies |

### Sample Detection Configurations

**Automatic Backend (Recommended):**
```json
{
  "model_type": "auto",
  "weights_path": "config/ultralytics/models/yolo11n.onnx"
}
```

**ONNX Runtime with Hardware Execution Providers:**
```json
{
  "model_type": "onnx",
  "weights_path": "config/ultralytics/models/yolo11n.onnx",
  "input_size": 640,
  "providers": ["CUDAExecutionProvider", "CPUExecutionProvider"]
}
```

**Intel OpenVINO:**
```json
{
  "model_type": "openvino",
  "weights_path": "config/ultralytics/models/yolo11n.onnx",
  "device": "CPU"
}
```

**Ultralytics YOLO / TensorRT Engine:**
```json
{
  "model_type": "yolo",
  "weights_path": "config/ultralytics/models/yolo11n.engine",
  "device": 0
}
```

### Adding a Custom Detection Backend

1. Subclass `BaseObjectDetectionService`:
   ```python
   from system.object_detection.base_object_detection import BaseObjectDetectionService, DetectionResult
   from system.object_detection.registry import register

   @register('my_detector')
   class MyDetector(BaseObjectDetectionService):
       def load_model(self, weights: str, **kwargs) -> None:
           # Initialize your detector model
           pass

       def detect(self, image, **kwargs) -> DetectionResult:
           # Run inference: return boxes_xyxy, confidences, classes
           pass
   ```
2. Import the module inside `system/object_detection/__init__.py`.
3. Set `"model_type": "my_detector"` in camera settings.

---

## ⚙️ Complete Configuration Guide (`config.json`)

The configuration file is divided into logical sections:

### 1. `general` — Global Application Settings

| Key | Description | Default |
|---|---|---|
| `debug` | Enable Flask debug mode | `true` |
| `system_check` | Print GPU/CUDA/PyTorch environment summary on startup | `true` |
| `log_path` | Application log file location | `"storage/logs/cvcounter.log"` |
| `log_level` | Minimum logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `"INFO"` |
| `log_console` | Mirror log output to terminal standard output | `false` |
| `default_language` | UI language (`"ru"`, `"en"`) | `"ru"` |
| `allow_unsafe_werkzeug` | Allow running Werkzeug server in production environments | `true` |
| `button_change_theme` | Display dark/light theme switch button | `true` |
| `button_fullscreen` | Display fullscreen toggle button | `true` |
| `button_backward` | Display back navigation button | `false` |
| `button_save_capture` | Display manual snapshot button on counter views | `false` |
| `collapsed_keyboard` | Show on-screen keyboard initially collapsed | `true` |

### 2. `server` — Web Server Options

| Key | Description | Default |
|---|---|---|
| `host` | Network listening address (`"0.0.0.0"` binds all adapters) | `"0.0.0.0"` |
| `port` | HTTP server port | `8080` |
| `use_reloader` | Auto-reload server process on code modification | `false` |
| `log_output` | Log incoming HTTP requests | `false` |
| `secret_key` | Flask session secret key (auto-generated if empty) | `""` |
| `allowed_origins` | CORS policy for Socket.IO | `"*"` |
| `socketio_async_mode` | Asynchronous runtime (`"threading"`, `"eventlet"`, `"gevent"`) | `"threading"` |
| `socketio_transports` | Allowed transport mechanisms | `["polling", "websocket"]` |
| `socketio_upgrade` | Permit transport upgrades from polling to WebSocket | `true` |
| `allow_web_control` | Allow server restart and shutdown actions from UI | `true` |

### 3. `datasets` — Dataset Limits

| Key | Description | Default |
|---|---|---|
| `max_upload_mb` | Maximum file size for image/ZIP uploads in MB | `512` |

### 4. `users` — Authentication Accounts

Passwords are stored as scrypt hashes:
```json
"users": {
    "admin": "scrypt:32768:8:1$rsdPYhqaQqpXQQ0o$aa3359c86228b4cee5fe8c4ed694db4b371fa7fab5100fa7b446db7e1ed8077e3bb63228d4a1899aeeef9b8d15f8e8bdbcc3457f020bcb3ec320332c76b5896b"
}
```
*(Default credentials: `admin` / `admin`)*.

### 5. `db` — Database Connection

| Key | Description | Default |
|---|---|---|
| `uri` | SQLAlchemy database connection URI | `"sqlite:///config/database.sqlite"` |
| `prefix` | Table prefix for database tables | `""` |

### 6. `telemetry` — Optional Diagnostics

| Key | Description | Default |
|---|---|---|
| `enabled` | Automatic transmission of anonymized error reports | `false` |
| `endpoint` | HTTPS receiver endpoint URL | `"https://bespredel.name/api/cvcounter/telemetry"` |
| `send_errors` | Send unhandled exceptions | `true` |
| `send_usage` | Send anonymized system usage events | `true` |
| `flush_interval_sec`| Interval for sending background telemetry batches (sec) | `300` |
| `timeout_sec` | HTTP timeout for telemetry requests | `5` |
| `hmac_secret` | Secret key for signing requests (`X-CVCounter-Signature`) | `""` |

### 7. `form` — Batch Form Custom Fields

Configures dynamic metadata fields collected during counting (e.g., lot number, shift, operator):
- `defect_show`: Display defect count entry form (`true`/`false`).
- `correct_show`: Display manual count correction form (`true`/`false`).
- `custom_fields`: Field definitions dictionary. Supported types: `text`, `number`, `textarea`, `date`, `datetime-local`, `select` (with `options` array).

### 8. `detection_default` and `detections.<location>`

Cameras configured under `detections` inherit missing values from `detection_default`:

| Key | Description | Example |
|---|---|---|
| `label` | Human-readable camera display title | `"Packaging Line #1"` |
| `video_path` | RTSP stream URL, video file path, or webcam index (`0`, `1`) | `"rtsp://admin:12345@192.168.1.10:554/ch1"` |
| `start_total_count` | Initial total count value | `0` |
| `model_type` | Model backend (`auto`, `yolo`, `onnx`, `openvino`, `opencv`) | `"auto"` |
| `weights_path` | Model file path | `"config/ultralytics/models/yolo11n.onnx"` |
| `confidence` | Minimum detection confidence score (0.0 – 1.0) | `0.6` |
| `iou` | Non-Maximum Suppression (IoU) threshold | `0.7` |
| `device` | Inference execution device (`0`, `"cpu"`, `"GPU"`, `"AUTO"`) | `0` |
| `vid_stride` | Frame stride (1: process all frames, 2: process every second frame) | `1` |
| `video_show_scale` | Downscaled stream resolution for browser streaming (%) | `70` |
| `video_show_quality` | JPEG compression quality for stream frames (1–100) | `50` |
| `video_fps` | Manual frame rate lock (0: match source) | `0` |
| `video_reconnect_attempts` | Connection retry limit before entering error state | `5` |
| `counting_areas` | Array of polygonal counting areas with BGR colors | `[{"points": [[0,0],[100,0],[100,100],[0,100]], "color": [67,211,255]}]` |
| `classes` | Class filter and custom labels for per-class counts | `{"0": "Carton", "1": "Pallet"}` |
| `recording.enable` | Enable event-driven video recording | `false` |
| `recording.path` | Destination directory for recorded clips | `"storage/saved_recordings"` |
| `recording.idle_timeout` | Idle seconds without detections before closing video clip | `30` |

---

## 🖥️ Web Interface & Operation Modes

### 1. Dashboard (`/`)
The command center:
- Live status badges for all counters (*Running*, *Paused*, *Stopped*).
- Real-time video thumbnails.
- Quick actions: Start, Pause, Stop, Reset, and Settings modal.
- Search and status filtering.

### 2. Video Counter View (`/counter/<location>`)
Primary workstation for line operators:
- Real-time video canvas with detection bounding boxes, tracker trails, and active zones.
- Metrics sidebar: **Total Count**, **Current Batch**, **Defects**, and **Corrections**.
- Collapsible **By Classes** breakdown showing `batch / total` statistics.
- Batch data entry form with database persistence.

### 3. Text-Only View (`/counter/<location>/text`)
High-efficiency view stripped of video streaming:
- Extremely low bandwidth and CPU consumption.
- Optimal for battery-powered warehouse handhelds and tablets.

### 4. Multi-Counter Grid (`/counter_multi/text?locations=Cam1,Cam2`)
Unified dashboard monitoring multiple lines simultaneously.

### 5. Interactive Zone Editor (`/counter/<location>/counting_area`)
Visual polygon tool operating directly over a camera freeze-frame:
- Create multiple polygons with distinct colors.
- Add, drag, and delete polygon vertices.
- Preset templates: "Full Frame", "Centered Rectangle".
- Immediate bidirectional sync with `config.json`.

### 6. Reports & A4 Printing (`/reports`)
- Searchable and paginated shift and batch history.
- Integrated video player and snapshot viewer for captured media.
- Dedicated A4 print layout: auto-light theme, stripped interface controls, formal metric tables, and approval sign-off blocks.

---

## 📚 Datasets, Annotation & Model Training

The `/datasets` suite provides end-to-end tooling for custom vision models:

1. **Dataset Creation:** Name, task selection (Detection / Segmentation), and class definitions.
2. **Data Ingestion:**
   - Upload local image folders or ZIP archives;
   - Live camera snapshots;
   - Interval-based frame capture from active video feeds;
   - Extracting frames from event recordings.
3. **Annotation:**
   - Bounding box and segmentation polygon tools;
   - Persistent Track IDs and object attribute tags;
   - Quick "copy previous annotations" shortcut for high-frame-rate sequences;
   - **Autolabeling:** Automated pre-annotation using standard foundation models;
   - **Active Learning:** Prioritizing uncertain frames to maximize training efficiency.
4. **Model Training:**
   - Select base models (YOLO11, YOLOv8, etc.);
   - Configure epochs, batch sizes, and image resolution;
   - Real-time training progress graphs;
   - Deploy `best.pt` model weights to any counter with 1 click.

---

## 🔌 REST API Reference

### Counter Operations (`routes/counters.py`)

| Method | URL | Description |
|---|---|---|
| `GET` | `/counter/<location>/bootstrap` | Initialize and start background counter thread |
| `GET`, `POST` | `/start_count/<location>` | Start or resume counting |
| `GET`, `POST` | `/pause_count/<location>` | Pause counting |
| `GET`, `POST` | `/stop_count/<location>` | Stop counter thread and release video resource |
| `POST` | `/save_count/<location>` | Save current batch and form data to database |
| `GET`, `POST` | `/reset_count/<location>` | Reset total counter to zero |
| `POST` | `/reset_count_current/<location>` | Reset current batch counter |
| `POST` | `/update_pending_counts/<location>` | Modify temporary uncommitted count / defect values |
| `GET`, `POST` | `/save_capture/<location>` | Save single camera frame snapshot to storage |
| `GET`, `POST` | `/counter/<location>/capture/interval` | Configure automated interval image capture |
| `GET` | `/counter_get_frames/<location>` | Stream live MJPEG video feed |
| `GET` | `/counter/<location>/preview` | Fetch latest JPEG preview thumbnail |
| `GET` | `/counter/<location>/settings/form` | Render HTML camera settings form for modals |
| `POST` | `/counter/<location>/settings` | Save camera detection parameters |
| `GET` | `/counter/<location>/counting_area/data` | Retrieve JSON coordinates of counting areas |
| `GET` | `/counter/<location>/counting_area/snapshot` | Fetch still frame for the zone editor canvas |
| `POST` | `/counter/<location>/counting_area` | Save updated counting area polygon coordinates |

### Settings & System (`routes/settings.py` — Authentication Required)

| Method | URL | Description |
|---|---|---|
| `POST` | `/settings_save` | Save global system configuration |
| `POST` | `/settings/api/detections/add` | Add a new camera to configuration |
| `POST` | `/settings/api/detections/<location>/delete` | Remove a camera from configuration |
| `POST` | `/settings/api/custom_fields/add` | Create a dynamic form field |
| `POST` | `/settings/api/custom_fields/delete` | Delete a dynamic form field |
| `POST` | `/settings/api/model_classes` | Inspect model file and extract class names automatically |
| `GET` | `/settings/api/runtimes/status` | Check installed hardware acceleration runtimes |
| `POST` | `/settings/api/runtimes/install` | Trigger automated installation of an inference runtime |
| `GET` | `/settings/api/runtimes/install/status` | Poll runtime installation progress |
| `GET` | `/settings/api/models/list` | List available model files in system directories |
| `POST` | `/settings/api/models/export` | Start model export task (ONNX, TensorRT Engine) |
| `GET` | `/settings/api/models/export/status` | Monitor model export progress |
| `GET` | `/settings/api/logs` | Fetch real-time system logs with filtering |
| `GET` | `/settings/api/logs/download` | Download full log file |
| `POST` | `/settings/api/logs/clear` | Clear log file |
| `POST` | `/settings/api/restart` | Restart the web server process |
| `POST` | `/settings/api/shutdown` | Shut down the web server process |

### Datasets (`routes/datasets.py` — Authentication Required)

| Method | URL | Description |
|---|---|---|
| `GET` | `/datasets/api/list` | List all datasets and their statuses |
| `POST` | `/datasets/api/create` | Create a new dataset |
| `DELETE` | `/datasets/api/<name>` | Delete a dataset |
| `GET` | `/datasets/api/<name>/summary` | Get image counts, class statistics, and annotations |
| `POST` | `/datasets/api/<name>/capture-camera` | Capture frame from camera directly to dataset |
| `POST` | `/datasets/api/<name>/import/upload` | Upload images or ZIP archive to dataset |
| `POST` | `/datasets/api/<name>/split` | Automatically split images into train/val subsets |
| `GET`, `POST`| `/datasets/api/<name>/annotations/<image>` | Read or write annotations for an image |
| `POST` | `/datasets/api/<name>/autolabel` | Batch auto-annotate dataset images |
| `POST` | `/datasets/api/<name>/train` | Launch YOLO model training job |
| `GET` | `/datasets/api/training/status` | Monitor training metrics and progress |
| `POST` | `/datasets/api/training/cancel` | Cancel active training run |
| `POST` | `/datasets/api/training/apply-weights` | Deploy `best.pt` weights to a camera detector |

---

## 🔐 Authentication & Security

- Session management uses cryptographically signed Flask session cookies.
- Credentials and scrypt password hashes are managed under `users` in `config/config.json`.
- When `users` is left empty, the application operates in open access mode.
- Protected endpoints (`@login_required`):
  - `/settings` (all configuration and runtime actions);
  - `/system_info` (system diagnostics, log console);
  - `/datasets` (all dataset creation, labeling, and training tasks).
- Public endpoints: Dashboard, counter monitors, reports viewer, and help center.

---

## ⚡ Real-Time Events (Socket.IO)

Browser clients receive instant updates via WebSocket/Socket.IO connections:

| Event Name | Payload | Purpose |
|---|---|---|
| `{location}_count` | `{total, current, defect, correct, pending_*, by_class: [...]}` | Live count values and class breakdown |
| `{location}_notification` | `{type: "success"|"warning"|"error", message: "..."}` | Operator notifications (saved batch, camera alert) |
| `counter_status_event` | `{data: {status: "started"|"paused"|"stopped"|"error", location: "..."}}` | Camera stream lifecycle state change |

---

## ❓ Frequently Asked Questions (FAQ)

### 1. What are the recommended server hardware specifications?
- **CPU:** Quad-core processor (Intel Core i5 / AMD Ryzen 5 or better).
- **RAM:** Minimum 8 GB (16 GB recommended for multiple concurrent streams).
- **GPU:**
  - *NVIDIA GeForce GTX 1050 Ti (4 GB):* Up to 5–6 concurrent live streams with YOLOv8n/YOLO11n.
  - *NVIDIA RTX 3060 / 4060 (8–12 GB):* 15–20 real-time streams or smooth local model training.
  - *Intel Arc / integrated iGPUs:* Excellent hardware acceleration via OpenVINO without discrete graphics.

### 2. How can I lock down the workstation for line operators?
Run Chrome or Chromium in kiosk mode:
```bash
google-chrome --kiosk --start-fullscreen http://localhost:8080/counter/Line1
```

### 3. What should I do if the RTSP stream drops frequently?
Increase `video_reconnect_attempts` (e.g., to `10` or `20`) in camera settings. The engine will transparently reconnect upon temporary network glitches.

### 4. Where are saved video recordings and snapshots stored?
All media is stored inside `storage/` (`storage/saved_recordings` and `storage/saved_images`), and can be browsed and downloaded from **Reports ➔ Saved Media**.

---

## 🤝 Contributing & License

Contributions, bug reports, and pull requests are warmly welcomed:
1. Fork [BespredeL/CVCounter](https://github.com/BespredeL/CVCounter).
2. Create your feature branch (`git checkout -b feature/my-feature`).
3. Commit your changes (`git commit -m 'Add awesome feature'`).
4. Push to branch (`git push origin feature/my-feature`) and open a Pull Request.

Distributed under the open-source **[GNU AGPLv3](https://github.com/BespredeL/CVCounter/blob/master/LICENSE)** license.
