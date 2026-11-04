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
- 🔄 **Multi-Object Tracking:** High-accuracy tracker maintaining persistent IDs between frames to prevent double-counting.
- 🏷️ **Per-Class Breakdown:** Real-time counters showing both total counts and current batch counts partitioned by detection classes.
- 🎥 **Flexible Video Inputs:** RTSP/RTMP network camera streams, local webcams (USB/V4L2), and pre-recorded video files.
- 🎬 **Event-Driven Recording:** Video clips start recording automatically upon object detection and stop following a configurable `idle_timeout`.
- 🧠 **Multi-Architecture Detection:** Seamless architecture and runtime support across Ultralytics YOLO, ONNX Runtime, RF-DETR, D-FINE, and RTMDet.
- 📚 **Full Dataset Workflow:** In-browser frame capture, bounding box/polygon annotation, active learning, autolabeling, YOLO + COCO export, training through pluggable providers (Ultralytics YOLO, torchvision), and 1-click model weight deployment.
- 📊 **Reports & Analytics:** Paginated session history, defect and manual correction logs, saved media playback, and A4 print-ready layouts with sign-off blocks.
- 🚀 **1-Click Installer:** Cross-platform scripts (`install.bat` / `install.sh`) automatically detecting GPUs (NVIDIA CUDA, AMD DirectML, Intel Arc / OpenVINO).
- 🛠️ **AI Runtimes Center:** In-app inspection and automated installation of missing inference libraries (CUDA, TensorRT, OpenVINO).
- 🔐 **Security:** Session authentication, administrative protection for settings and datasets, and scrypt password hashing.

---

## 🏛️ Application Architecture

CVCounter is designed as a layered, modular platform with strict separation of concerns across video ingestion, computer vision inference, tracking, counting logic, web UI, and background workers.

### Video Frame Processing & Data Pipeline:

```mermaid
flowchart TD
    A[Video Source<br>RTSP / WebCam / File] --> B[VideoStreamManager / VideoCapture]
    B --> C[CounterLoop<br>Dedicated Background Processing Thread]
    C --> D[IDetector<br>YOLO / ONNX / DETR / DFINE / RTMDet]
    D -->|DetectionFrameResult| E[ByteTracker<br>Persistent ID Assignment]
    E --> F[CountKernel<br>Polygon & Zone Intersection Logic]
    F --> G[CountState<br>Per-Class Counts, Batches, Defects]
    G --> H[FrameRenderer<br>Bounding Boxes, Zones & HUD Overlays]
    H --> I[MJPEG Streamer<br>Live Video to Browser Operator]
    G --> J[DatabaseManager<br>Persistence to SQLite / MySQL]
    G --> K[Socket.IO Server<br>Real-Time Dashboard Telemetry]
    C --> L[RecordingControl<br>Event-Driven Video Clip Recording]
```

### Project Structure:

```
CVCounter/
├── app.py                      # Application entrypoint & WSGI runner
├── train.py                    # Standalone CLI training & export engine
├── install.py                  # Cross-platform automated setup script with GPU detection
├── config/                     # Configuration files, models & database
│   ├── config.json             # Active configuration file
│   ├── config.example.json     # Reference default configuration
│   ├── database.sqlite         # SQLite database (sessions, batch history, defects)
│   ├── ultralytics/            # Ultralytics YOLO configs, base checkpoints, and runs
│   └── torchvision/            # torchvision configs, base checkpoints, and runs
├── routes/                     # Blueprint controllers (Presentation Layer)
│   ├── main.py                 # Dashboard, authentication (/login, /logout), help
│   ├── counters.py             # Counter screens, MJPEG streaming, polygon editor
│   ├── reports.py              # Reports viewer, saved media playback, A4 PDF print
│   ├── datasets.py             # Frame capture, annotation, training, and autolabeling
│   ├── settings/               # Modular settings package (cameras, models, runtimes, logs, API keys)
│   └── api/                    # REST API v1 (/api/v1/counters, /api/v1/reports, /api/v1/system)
├── system/                     # Core Application Layer
│   ├── app_factory.py          # Application Factory (Flask app & Socket.IO initialization)
│   ├── runtime.py              # AppRuntime (singleton registry & runtime state container)
│   ├── auth/                   # Session authentication, API token validation, scrypt hashing
│   ├── core/                   # Video pipeline: ObjectCounter, CounterLoop, ByteTrack, FrameRenderer
│   ├── db/                     # SQLAlchemy ORM models, migrations & data repositories
│   ├── detection/              # Unified detection engine: IDetector, standalone adapters, registry
│   ├── managers/               # Video streams, worker threads, database, notifications, training jobs
│   ├── services/               # Service layer: counter state, event dispatching, count store
│   ├── datasets/               # Dataset service, sequence leakage validation, YOLO/COCO converters
│   ├── training/               # TrainingEngine, provider registry (Ultralytics, torchvision), export
│   └── utils/                  # I18n, telemetry, validators, logger, hardware GPU inspection
├── static/                     # Static UI assets (CSS, JS, fonts, icons)
├── templates/                  # Jinja2 HTML templates
└── storage/                    # Persistent storage (logs, snapshots, recordings, datasets)
```

### Core Blueprints:

| Blueprint | Module / Package | URL Prefix | Purpose |
|---|---|---|---|
| `main` | `routes/main.py` | `/` | Dashboard, authentication (`/login`, `/logout`), help (`/page/help`) |
| `counters` | `routes/counters.py` | `/` | Counter screens, MJPEG video, zone editor, batch recording |
| `reports` | `routes/reports.py` | `/reports` | Session histories, captured media viewer, printable A4 layouts |
| `datasets` | `routes/datasets.py` | `/datasets` | Data preparation, image annotation, model training (*auth*) |
| `settings` | `routes/settings/` | `/settings`, `/system_info` | Camera configuration, AI runtimes, log terminal, models (*auth*) |
| `api_v1` | `routes/api/v1/` | `/api/v1` | Programmatic REST API v1: counter metrics, reports, system health |

---

## 📦 Installation & Deployment

### Method 1: Automatic 1-Click Installation (Recommended)

The `install.py` script detects a hardware profile but installs only Core dependencies by default. ML runtimes and PyTorch/Ultralytics are installed only when explicitly requested:

- **Windows:** Double-click **`install.bat`**. Launch the app with **`start.bat`**.
- **Linux / macOS:**
  ```bash
  chmod +x install.sh start.sh
  ./install.sh
  ./start.sh
  ```

#### Supported Acceleration Profiles:
- **`nvidia_cuda`:** NVIDIA target profile; `--with-inference` installs `onnxruntime-gpu`, while `--with-pytorch` installs a compatible PyTorch build.
- **`amd_directml`:** AMD target profile; `--with-inference` installs ONNX Runtime DirectML.
- **`intel_openvino`:** Intel target profile; `--with-inference` installs OpenVINO and ONNX Runtime.
- **`cpu`:** CPU target profile; `--with-inference` installs ONNX Runtime CPU.

Installer options:
```bash
python install.py --profile nvidia_cuda  # Force hardware acceleration profile
python install.py --with-inference       # Install inference runtime for the selected profile
python install.py --with-ultralytics     # PyTorch + Ultralytics (.pt models and YOLO training)
python install.py --with-pytorch         # PyTorch provider only
python install.py --provider onnxruntime --provider openvino  # Select multiple built-in runtimes
python install.py --provider opencv       # OpenCV DNN is included in Core; no extra package
python install.py --reinstall            # Force package reinstallation
python install.py --no-color             # Disable ANSI colored output
```

`--provider` accepts `onnxruntime`, `openvino`, `opencv`, `pytorch`, or
`ultralytics` and can be repeated. The legacy `--with-inference` option remains
available and installs the runtime combination selected for the detected or
forced hardware profile.

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

   # Optional: ONNX Runtime CPU inference
   pip install -r requirements-onnxruntime.txt
   
   # Optional: For YOLO training and .pt weights
   pip install -r requirements-ultralytics.txt

   # Optional: For Intel OpenVINO acceleration
   pip install -r requirements-openvino.txt

   # Optional: ONNX export/optimization tools
   pip install -r requirements-onnx-export.txt
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

The unified detection subsystem (`system/detection/`) provides a standardized `IDetector` interface (`system/detection/interface.py`) and a centralized factory `load_detector` (`system/detection/registry.py`). The subsystem completely decouples diverse model architectures (Ultralytics YOLO, Generic ONNX, RF-DETR, D-FINE, RTMDet) from the video pipeline.

Each detector returns a structured `DetectionFrameResult` containing a list of `Detection` objects and a `.to_tracker_array() -> np.ndarray(N, 6)` method formatted as `[x1, y1, x2, y2, score, class_id]` consumed directly by ByteTrack.

> For a comprehensive walkthrough of the multi-architecture detection platform, CPU/CUDA inference, fine-tuning, and export workflows, see the [Multi-Architecture Platform Guide](multi_architecture_guide.md).

### Optional Model Manifest

An optional `<model-stem>.manifest.json` sidecar can declare model details without assuming that a file extension identifies its architecture or output format:

```json
{
  "schema_version": 1,
  "architecture": "yolo",
  "task": "object_detection",
  "format": "onnx",
  "runtime": "onnxruntime",
  "preprocessing": {
    "color_order": "BGR",
    "resize": "letterbox"
  },
  "input_contract": {
    "dtype": "float32",
    "layout": "NCHW",
    "shape": [1, 3, 640, 640]
  },
  "output_contract": {
    "layout": "BNC",
    "coordinates": "xywh"
  },
  "decoder": "yolo_outputs"
}
```

Preprocessing, tensor input, output, and decoder declarations are separate so a model is not assumed compatible merely because a runtime can open its artifact. The postprocessing module (`system/detection/postprocessing.py`) supports `yolo_outputs` (anchor grids and end-to-end `[N, 6]` tensors), `detr_outputs` (class logits and normalized boxes for DETR/RF-DETR/D-FINE), and `rtmdet_outputs`. Canonical ONNX models are executed via ONNX Runtime (`system/detection/backends/onnx_session.py`) with dynamic Execution Provider selection (CUDA, OpenVINO, DirectML, CPU).

### Supported `model_type` Options:

| `model_type` | Architecture / Engine | License | Formats | Best Use Case |
|---|---|---|---|---|
| **`auto`** | Auto-selection | — | `.onnx`, `.pt`, `.engine`, `.pth` | **Default.** Automatically identifies architecture from filename and format |
| **`yolo`**, `ultralytics` | [Ultralytics YOLO](https://github.com/ultralytics/ultralytics) | AGPL-3.0 | `.pt`, `.engine` (TensorRT) | YOLOv8–YOLO26, native PyTorch, TensorRT engines, model training |
| **`onnx`**, `onnxruntime` | [ONNX Runtime](https://onnxruntime.ai/) | MIT | `.onnx` (YOLO, DETR, RTMDet) | Maximum cross-platform throughput (CUDA, DirectML, OpenVINO, CPU) |
| **`rf_detr`** | [Roboflow RF-DETR](https://github.com/roboflow/rf-detr) | Apache-2.0 | `.pth`, `.pt`, `.onnx` | Transformer RF-DETR detectors (Nano, Small, Medium, Large) |
| **`d_fine`** | [Peterande D-FINE](https://github.com/Peterande/D-FINE) | Apache-2.0 | `.pth`, `.pt`, `.onnx` | Real-time DETR with fine-grained distribution refinement (N/S/M/L/X) |
| **`rtmdet`** | [OpenMMLab RTMDet](https://github.com/open-mmlab/mmdetection) | Apache-2.0 | `.pth`, `.onnx` | High-speed OpenMMLab RTMDet detectors (Tiny, S, M, L, X) |

### Sample Detection Configurations

**Automatic Backend (Recommended):**
```json
{
  "model_type": "auto",
  "weights_path": "config/ultralytics/models/yolo11n.onnx"
}
```

**ONNX Runtime with Hardware Execution Providers (CUDA):**
```json
{
  "model_type": "onnx",
  "weights_path": "config/ultralytics/models/yolo11n.onnx",
  "input_size": 640,
  "providers": ["CUDAExecutionProvider", "CPUExecutionProvider"]
}
```

**ONNX Runtime with OpenVINO Execution Provider (Intel CPUs, iGPUs, Arc GPUs):**
```json
{
  "model_type": "onnx",
  "weights_path": "config/ultralytics/models/yolo11n.onnx",
  "device": "cpu",
  "providers": ["OpenVINOExecutionProvider", "CPUExecutionProvider"]
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

1. Subclass `IDetector`:
   ```python
   import numpy as np
   from system.detection import IDetector, DetectionFrameResult, Detection, register_detector

   class MyDetector(IDetector):
       def __init__(self, weights: str, **kwargs):
           self.weights = weights
           # Initialize your detector model

       def is_loaded(self) -> bool:
           return True

       def unload(self) -> None:
           pass

       def detect(self, frame: np.ndarray) -> DetectionFrameResult:
           # Run inference and construct result
           h, w = frame.shape[:2]
           detections = [
               Detection(
                   class_id=0, class_name="box", confidence=0.95,
                   x1=100.0, y1=150.0, x2=200.0, y2=250.0
               )
           ]
           return DetectionFrameResult(detections=detections, image_width=w, image_height=h)

       def get_classes(self) -> dict[int, str]:
           return {0: "box"}

       def close(self) -> None:
           self.unload()

   # Register detector factory in the registry
   register_detector("my_detector", lambda **kwargs: MyDetector(**kwargs))
   ```
2. Set `"model_type": "my_detector"` in camera settings.

---

## ⚙️ Complete Configuration Guide (`config.json`)

The configuration file is divided into logical sections:

### 1. `general` — Global Application Settings

| Key | Description | Default |
|---|---|---|
| `debug` | Enable Flask debug mode | `true` |
| `system_check` | Print available GPU/runtime and optional PyTorch status on startup | `true` |
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

### 6. `telemetry` — Diagnostics and Telemetry

| Key | Description | Default |
|---|---|---|
| `enabled` | Automatic transmission of pseudonymized error reports | `true` |
| `endpoint` | HTTPS receiver endpoint URL | `"https://bespredel.name/api/cvcounter/telemetry"` |
| `send_errors` | Send unhandled exceptions | `true` |
| `send_usage` | Send pseudonymized system usage events (camera labels travel as stable aliases) | `true` |
| `flush_interval_sec`| Interval for sending background telemetry batches (sec) | `3600` |
| `max_batch_size` | Maximum events per HTTP request; also flushes early when the buffer fills | `200` |
| `max_queue_size` | Maximum in-memory command queue size | `400` |
| `error_dedup_sec` | Window that suppresses identical error reports (sec) | `600` |
| `timeout_sec` | HTTP timeout for telemetry requests | `10` |
| `hmac_secret` | Secret key for signing requests (`X-CVCounter-Signature`) | `""` |
| `compress` | Gzip compression for telemetry batches | `true` |

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
| `model_type` | Model architecture (`auto`, `ultralytics`, `onnx`, `rf_detr`, `d_fine`, `rtmdet`) | `"auto"` |
| `weights_path` | Model file path | `"config/ultralytics/models/yolo11n.onnx"` |
| `confidence` | Minimum detection confidence score (0.0 – 1.0) | `0.6` |
| `iou` | Non-Maximum Suppression (IoU) threshold | `0.7` |
| `device` | Inference execution device (`0`, `"cpu"`, `"GPU"`, `"AUTO"`) | `0` |
| `vid_stride` | Frame stride (1: process all frames, 2: process every second frame) | `1` |
| `video_show_scale` | Downscaled stream resolution for browser streaming (%) | `70` |
| `video_show_quality` | JPEG compression quality for stream frames (1–100) | `50` |
| `video_fps` | Manual frame rate lock (0: match source) | `0` |
| `video_reconnect_attempts` | Connection retry limit before entering error state | `5` |
| `counting_areas` | Array of polygonal counting areas with BGR colors and motion direction | `[{"points": [[0,0],[100,0],[100,100],[0,100]], "color": [67,211,255], "direction": "top_to_bottom"}]` |
| `classes` | Class filter and custom labels for per-class counts | `{"0": "Carton", "1": "Pallet"}` |
| `dataset_create.enable` | Enable automatic dataset frame collection | `false` |
| `dataset_create.probability` | Sampling probability for frame saving (0.0 – 1.0) | `0.1` |
| `dataset_create.path` | Base directory for captured frames (camera subfolder created automatically) | `"storage/saved_images"` |
| `recording.enable` | Enable event-driven video recording | `false` |
| `recording.path` | Base directory for recorded video clips (camera subfolder created automatically) | `"storage/saved_recordings"` |
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
- **Motion direction filtering:** 8 directional vectors (cardinal & diagonal) or "Any direction" per zone with $\pm 60^\circ$ angular cone acceptance and dynamic directional arrow overlay at zone center.
- Add, drag, and delete polygon vertices.
- Preset templates: "Full Frame", "Centered Rectangle".
- Layout-independent keyboard shortcuts (RU/EN), Undo/Redo history (`Ctrl+Z`, `Ctrl+Y`).
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
   - Bounding box (`W`) and segmentation polygon (`P`) tools;
   - Layout-independent keyboard shortcuts (RU/EN), frame stepping (`A`/`D` or `←`/`→`), Undo/Redo (`Ctrl+Z`, `Ctrl+Y`);
   - Persistent Track IDs and object attribute tags;
   - Quick "copy previous annotations" shortcut for high-frame-rate sequences;
   - **Autolabeling:** Automated pre-annotation using standard foundation models (`Ctrl+A`);
   - **Active Learning:** Prioritizing uncertain frames to maximize training efficiency.
4. **Model Training:**
   - Select a training provider — training is not tied to any single framework;
   - Pick a base checkpoint from the catalog the chosen provider can actually download;
   - Configure epochs, batch sizes, and image resolution;
   - Real-time training progress graphs;
   - Deploy the trained weights to any counter with 1 click.

### Training Providers

Training capabilities are declared, not assumed: `BuiltinTrainingProvider`
(`system/training/registry.py`) lists the tasks, dataset formats, export formats and
architectures a provider genuinely supports. The UI and the API only offer what a provider
declares, so a job that asks it to export a format it cannot produce never gets queued.

| Provider | Tasks | Dataset format | Export | Dependency install | License |
|---|---|---|---|---|---|
| `ultralytics` | `detect`, `segment`, `classify`, `pose` | `yolo` (`.txt` + `data.yaml`) | `onnx`, `engine` | `python install.py --provider ultralytics` | AGPL-3.0 |
| `torchvision` | `detect` | `coco` (COCO JSON) | *not implemented* | `python install.py --provider pytorch` | BSD-3-Clause |

- Every provider keeps its configs, base weights and runs under `config/<provider>/{cfg,models,runs}`;
  Ultralytics keeps the historic `config/ultralytics/` layout with a fallback to the legacy
  `config/{cfg,models,runs}`.
- Runs are discovered without importing the framework: `list_runs()` and `find_run_weights()`
  look for `weights/best.pt`, `weights/model_final.pt`, `weights/best.pth` and `weights/model_final.pth`.
- `torchvision` fine-tunes Faster R-CNN (`fasterrcnn_resnet50_fpn_v2`) from COCO annotations
  but does not yet emit a deployable model file. Its training tab shows a warning about that
  and offers no export format.
- The "apply weights to a camera" step only lists artifacts the detection registry can load
  (Ultralytics `.pt`, `.onnx`, `.engine`); checkpoints from providers without export stay in
  `/datasets/api/training/runs` and never appear in the deploy dropdown.

To add your own provider, subclass `BaseTrainingProvider` (`system/training/base.py`),
implement `train()` — the only abstract method — plus `export()`, `prepare()`,
`base_models()`, `supports_base_model()` or `download_base_model()` as needed, then register a
`BuiltinTrainingProvider(...)` entry in `_BUILTIN_TRAINING_PROVIDERS`. The registry imports the
class lazily and probes dependencies with `importlib.util.find_spec`, so a missing framework
does not break the app: the provider simply reports status `unavailable` and the UI suggests the
install command from its `install_provider` field.

### Dataset Export Formats

`export_for_training(name, dataset_format)` writes one of `'yolo'`, `'coco'` or `'both'`; the
`dataset_format` (alias `format`) parameter is accepted by the UI and by
`POST /datasets/api/<name>/export`. The framework-neutral dataset looks like this:

```
storage/datasets/<name>/
├── images/{train,val}/…                     # source frames
└── coco/annotations/instances_{split}.json  # COCO detection
```

Each JSON is standard COCO detection (`categories` with 1-based `id`, `bbox [x, y, w, h]` in
absolute pixels, `area`, plus `segmentation` for the `segment` task) extended with project keys:
top-level `task`, `split` and `root`, and a `path` on every image entry. A provider resolves
frames through them, falling back to three levels up from the annotation file when `root` is
absent.

### Standalone `train.py` CLI

```bash
python train.py providers
python train.py list --provider ultralytics
python train.py list --provider torchvision
python train.py train --config road-map --provider ultralytics --epochs 100 --export onnx
python train.py train --config road-map --provider torchvision --epochs 20 --imgsz 800 --batch 2
python train.py export --config road-map --provider ultralytics --export engine
```

`--provider auto` selects the provider from the task and dataset format, `--dataset-format`
states it explicitly, and `train.py` refuses to start a job the selected provider does not
declare.

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

### Settings & System (package `routes/settings/` — Authentication Required)

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
| `POST` | `/datasets/api/<name>/export` | Export the dataset as `yolo`, `coco` or `both` (`dataset_format`) |
| `GET` | `/datasets/api/<name>/export-zip` | ZIP archive of the dataset in both formats |
| `POST` | `/datasets/api/<name>/autolabel` | Batch auto-annotate dataset images |
| `GET` | `/datasets/api/models/base` | Base checkpoint catalog of a provider (`?provider=`) |
| `POST` | `/datasets/api/<name>/train` | Launch a training job (`provider`, `base_model`) |
| `GET` | `/datasets/api/training/status` | Monitor training metrics and progress |
| `POST` | `/datasets/api/training/cancel` | Cancel active training run |
| `GET` | `/datasets/api/training/runs` | List finished runs (`?provider=`, `?task=`) |
| `POST` | `/datasets/api/training/apply-weights` | Deploy trained weights to a camera detector |

### Programmatic REST API v1 (package `routes/api/v1/` — Prefix `/api/v1`)

| Method | URL | Description |
|---|---|---|
| `GET` | `/api/v1/counters` | List all configured counters and their current execution status |
| `GET` | `/api/v1/counters/<location>` | Retrieve metrics and state for a specific counter |
| `POST` | `/api/v1/counters/<location>/start` | Start counting on a counter |
| `POST` | `/api/v1/counters/<location>/pause` | Pause counting |
| `POST` | `/api/v1/counters/<location>/stop` | Stop counter and release video source |
| `POST` | `/api/v1/counters/<location>/reset` | Reset total counter metrics |
| `POST` | `/api/v1/counters/<location>/save` | Save current batch count and form fields |
| `GET` | `/api/v1/counters/<location>/snapshot` | Capture current still frame |
| `GET` | `/api/v1/reports` | List saved session reports |
| `GET` | `/api/v1/reports/<id>` | Fetch detailed report record |
| `DELETE` | `/api/v1/reports/<id>` | Delete report record from database |
| `GET` | `/api/v1/system/health` | Service health check endpoint |
| `GET` | `/api/v1/system/info` | System diagnostic details (version, OS, GPU, available runtimes) |

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
All media is stored inside `storage/`:
- **Video recordings:** `<recording.path>/<camera_id>/` (default: `storage/saved_recordings/<camera_id>/`)
- **Captured frames / datasets:** `<dataset_create.path>/<camera_id>/` (default: `storage/saved_images/<camera_id>/`)

The base directory is defined in configuration, and subfolders for each camera are created automatically. All recordings and frames can be browsed, played, and downloaded from **Reports ➔ Saved Media**.

---

## 🤝 Contributing & License

Contributions, bug reports, and pull requests are warmly welcomed:
1. Fork [BespredeL/CVCounter](https://github.com/BespredeL/CVCounter).
2. Create your feature branch (`git checkout -b feature/my-feature`).
3. Commit your changes (`git commit -m 'Add awesome feature'`).
4. Push to branch (`git push origin feature/my-feature`) and open a Pull Request.

Distributed under the open-source **[GNU AGPLv3](https://github.com/BespredeL/CVCounter/blob/master/LICENSE)** license.

Training providers bring their own terms: Ultralytics is **AGPL-3.0**, while PyTorch and
torchvision are **BSD-3-Clause**. Installing only the `pytorch` provider keeps Ultralytics out
of the training path.
