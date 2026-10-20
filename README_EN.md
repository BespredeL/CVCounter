# CVCounter - Real-Time Object Detection & Counting System

[![Website](https://img.shields.io/badge/website-cvcounter.createdby.ru-4dabf7.svg)](https://cvcounter.createdby.ru)
[![Author](https://img.shields.io/badge/author-bespredel.name-8a2be2.svg)](https://bespredel.name)
[![Readme EN](https://img.shields.io/badge/README-EN-blue.svg)](https://github.com/BespredeL/CVCounter/blob/master/README_EN.md)
[![Readme RU](https://img.shields.io/badge/README-RU-blue.svg)](https://github.com/BespredeL/CVCounter/blob/master/README.md)
[![GitHub license](https://img.shields.io/badge/license-AGPL--3.0-458a7b.svg)](https://github.com/BespredeL/CVCounter/blob/master/LICENSE)

🧠 Production-ready computer vision system for real-time object detection, tracking, and counting.

CVCounter is a flexible and high-performance web-based computer vision system designed for live video stream analysis. Delivered as a self-hosted Flask web application, it eliminates the need to install any client-side software on operator workstations.

---

## ✨ Features

- 🎯 **Detection & Tracking:** Robust ByteTrack object tracking and real-time counting across single or multiple customizable polygon zones.
- 🎥 **Video Sources:** Support for RTSP network streams, USB/webcams, and local video files, with automatic event-driven video recording.
- 🏷️ **Classification:** Object counting broken down by classes with flexible class filtering.
- 📚 **Dataset Management:** In-browser frame capture (from stream, ZIP upload, recordings), bounding box/polygon annotation, YOLO training, and one-click deployment of trained `best.pt` weights.
- 🧠 **Multi-Backend Inference:** Support for ONNX Runtime, Intel OpenVINO, OpenCV DNN, and Ultralytics YOLO.
- 📊 **Reports & Analytics:** Batch and shift history, class breakdowns, saved media viewer, and export/printing in A4 format.
- 🚀 **1-Click Automated Setup:** Installer automatically detects GPUs (NVIDIA CUDA, AMD DirectML, Intel OpenVINO) and configures the environment.
- 🛠️ **Runtime Management:** Hardware acceleration diagnostics and one-click installation of missing inference libraries directly from the UI.
- 🔌 **REST API v1:** Full programmatic interface for integrations with CRM, ERP, Telegram bots, and external systems (API key authentication, access roles, counter controls, report queries, and camera snapshots). Read more: [`docs/api.md`](docs/api.md).
- 🔐 **Web Interface:** User authentication, visual zone editor, dynamic batch form fields, event logs, and real-time system diagnostics.

> [!TIP]
> **Optional Telemetry:**  
> You can enable anonymous error and usage reporting (`telemetry.enabled: true` in settings) to help improve the project.  
> Video frames, camera URLs, and passwords are **never sent**.  
> Read more: [`docs/telemetry_api.md`](docs/telemetry_api.md).

---

## 🚀 Use Cases

- 🏭 **Manufacturing & Logistics:** Counting products on conveyor belts, monitoring crates and pallets.
- 🏬 **Retail & Malls:** Customer counting, queue monitoring, and foot-traffic analytics.
- 🚗 **Traffic & Parking:** Vehicle counting and flow analysis.
- 🛡️ **Security & Surveillance:** Perimeter crossing and restricted area monitoring.

---

## 🧠 How It Works

```mermaid
flowchart LR
    A[Video Stream<br>RTSP / Camera / File] --> B[Object Detection<br>YOLO / ONNX / OpenVINO]
    B --> C[ByteTrack Tracker<br>Assign Track ID]
    C --> D{Zone<br>Intersection?}
    D -- Yes --> E[Record Count<br>Classes / Batches]
    E --> F[Web UI,<br>Reports & Media Storage]
```

1. **Video Ingestion:** Continuous frame reading from an IP camera, webcam, or video file.
2. **Inference:** Object detection using the configured model and backend.
3. **Tracking (ByteTrack):** Persistent ID assignment across frames to prevent double-counting.
4. **Zone Monitoring:** Triggering counts when an object enters any defined polygonal zone.
5. **Reporting & Persistence:** Live counter updates, per-class breakdown, and database persistence.

---

## 📦 Installation

### Method 1: Automatic 1-Click Installation (Recommended)

The installer automatically identifies your hardware acceleration profile (NVIDIA CUDA, AMD DirectML, Intel OpenVINO, or CPU), creates a virtual environment, installs the required packages, and prepares the configuration:

- **Windows:**  
  Double-click **`install.bat`**.  
  To launch the app, double-click **`start.bat`**.

- **Linux / macOS:**
  ```bash
  chmod +x install.sh start.sh
  ./install.sh
  ./start.sh
  ```

> **Installer CLI options (`install.py`):**
> - `--profile [nvidia_cuda|amd_directml|intel_openvino|cpu]` — Manually force hardware profile
> - `--reinstall` — Force reinstallation of packages
> - `--no-color` — Disable colored console output

---

### Method 2: Manual Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/BespredeL/CVCounter.git
   cd CVCounter
   ```

2. **Create and activate a virtual environment:**
   - **Windows:**
     ```bash
     python -m venv venv
     .\venv\Scripts\activate
     ```
   - **Linux / macOS:**
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

3. **Install core dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   *(Optional)* For PyTorch `.pt` models and YOLO training:
   ```bash
   pip install -r requirements-ultralytics.txt
   ```
   *(Optional)* For Intel OpenVINO acceleration:
   ```bash
   pip install -r requirements-openvino.txt
   ```

4. **Prepare the configuration file:**
   ```bash
   cp config/config.example.json config/config.json
   ```

5. **Start the application:**
   ```bash
   python app.py
   ```
   Open your browser at `http://localhost:8080` (default login/password: `admin` / `admin`).

---

### Method 3: Docker Compose

```bash
git clone https://github.com/BespredeL/CVCounter.git
cd CVCounter
docker-compose up --build
```

---

## 🖥️ Usage & Operating Modes

The web interface is optimized for operators on desktop screens and tablets:

1. **Primary Counter View (`/counters/<label>`)** — Live video stream with overlaid detection boxes, counting zones, real-time counters, defect/correction inputs, and batch controls.
2. **Text-Only View (`/counters/<label>/text`)** — Lightweight screen displaying only counters to conserve bandwidth and reduce client load.
3. **Multi-Camera Grid (`/counters/multi/text`)** — Unified summary view for monitoring all counters on a single screen.
4. **Datasets (`/datasets`)** — Frame capture, dataset annotation (boxes/polygons), and YOLO model training directly from your browser.
5. **Reports (`/reports`)** — Searchable count history, recorded event clips and snapshots, with A4 print and export options.

> [!TIP]
> **Operator Kiosk Mode:**  
> To prevent operators from closing the browser or navigating away:  
> `google-chrome --kiosk --start-fullscreen http://localhost:8080/counters/ExampleCam`

> **Performance Reference:**  
> On a modest setup (AMD Ryzen 5 3600, NVIDIA GTX 1050 Ti 4GB), the system smoothly handles 5–6 concurrent live video feeds with real-time detection.

---

## 📚 Datasets & Training

The built-in dataset suite lets you train custom vision models tailored to your specific objects:

1. Create a dataset and add images (via browser upload, ZIP file, or automatic capture from the camera feed).
2. Annotate images with bounding boxes or polygons.
3. Start training directly from the UI.
4. Apply the resulting `best.pt` model weights to any counter with a single click.

You can also manage training via the CLI:
```bash
python train.py list
python train.py train --config my-dataset --epochs 100
python train.py export --config my-dataset --export onnx
```

---

## 🧠 Supported Inference Backends

Configure the `model_type` setting per counter (or leave as `"auto"` for automatic detection based on file extension):

| `model_type` | Backend Engine | License | Supported Model Formats | Notes |
|---|---|---|---|---|
| **`auto`** | Auto-detection | — | `.onnx`, `.pt`, `.engine`, `.xml` | Recommended: automatically chooses backend from file extension |
| **`onnx`**, `onnxruntime` | [ONNX Runtime](https://onnxruntime.ai/) | MIT | `.onnx` (YOLOv5–v11, RT-DETR) | Fast, cross-platform (CUDA, DirectML, CPU) |
| **`openvino`** | [Intel OpenVINO](https://www.intel.com/openvino) | Apache-2.0 | `.xml`/`.bin`, `.onnx` | Optimized for Intel CPUs, iGPUs, Arc, and NPUs |
| **`yolo`**, `ultralytics` | [Ultralytics YOLO](https://github.com/ultralytics/ultralytics) | AGPL-3.0 | `.pt`, `.engine` (TensorRT) | Native PyTorch, model training, and tracking |
| **`opencv`**, `opencv_dnn` | [OpenCV DNN](https://docs.opencv.org) | Apache-2.0 | `.onnx`, Darknet (`.weights` + `.cfg`) | Lightweight, no heavy PyTorch dependencies |

### Key Detection Parameters

| Parameter | Applicable To | Description |
|---|---|---|
| `weights_path` | All | Path to model file (`.onnx`, `.pt`, `.xml`, etc.) |
| `confidence`, `iou` | All | Detection confidence threshold and NMS IoU threshold |
| `device` | YOLO, ONNX, OpenVINO | Inference device (`0`, `cpu`, `GPU`, `AUTO`) |
| `input_size` | ONNX, OpenVINO, OpenCV | Model input size (`640` or `[640, 640]`) |
| `vid_stride` | All | Frame stride (skip frames to reduce CPU/GPU load) |
| `classes` | All | Class filter and custom labels, e.g. `{"0": "Box"}` |
| `counting_areas` | All | List of polygon counting zones and their BGR colors |

---

## ⚙️ Configuration

System settings are stored in `config/config.json`. On initial startup, it is automatically generated from `config/config.example.json`.

Sample configuration structure:

```json5
{
    "general": {
        "debug": false,
        "default_language": "en",
        "log_path": "storage/logs/cvcounter.log"
    },
    "server": {
        "host": "0.0.0.0",
        "port": 8080
    },
    "db": {
        "uri": "sqlite:///config/database.sqlite"
    },
    "detection_default": {
        "model_type": "auto",
        "weights_path": "config/ultralytics/models/yolo11n.onnx",
        "confidence": 0.6,
        "iou": 0.7,
        "device": 0,
        "video_show_scale": 70,
        "video_show_quality": 50
    },
    "detections": {
        "Camera1": {
            "label": "Packaging Line #1",
            "video_path": "rtsp://admin:pass@192.168.1.50:554/stream1",
            "model_type": "auto",
            "weights_path": "config/ultralytics/models/yolo11n.onnx",
            "confidence": 0.65
        }
    }
}
```

> Full documentation of all settings (video recording, custom form fields, telemetry, zone setup) is available in [config/config.example.json](config/config.example.json) and in the [Wiki](docs/wiki.md).

---

## 📸 Screenshots

<p align="center">
  <img src="docs/en/images/Index.png" alt="Home page" width="85%">
</p>

<p align="center">
  <img src="docs/en/images/CounterVideo.png" alt="Video counter with detection zone" width="85%">
</p>

<p align="center">
  <img src="docs/en/images/ReportsIndex.png" alt="Reports and analytics" width="85%">
</p>

<details>
<summary><b>View all screenshots (9 more)</b></summary>
<br>

| Description | Screenshot |
|---|---|
| **Counting Zone Editor** | <img src="docs/en/images/CounterArea.png" alt="Setting up a counting area"> |
| **Camera Settings Modal** | <img src="docs/en/images/CounterModalSetting.png" alt="Camera Setup"> |
| **Text-Only Mode** | <img src="docs/en/images/CounterText.png" alt="Text Counter"> |
| **Multi-Counter Screen** | <img src="docs/en/images/CounterMultiText.png" alt="Multi Counters"> |
| **Counter Reports List** | <img src="docs/en/images/ReportsItems.png" alt="Counter Reports"> |
| **Detailed Report View** | <img src="docs/en/images/ReportsItemShow.png" alt="View the report"> |
| **System Settings** | <img src="docs/en/images/Settings.png" alt="Settings"> |
| **System Information** | <img src="docs/en/images/SystemInfo.png" alt="System Information"> |
| **Help & Docs** | <img src="docs/en/images/Help.png" alt="Help page"> |

</details>

---

## 👨‍💻 Author

**Aleksandr Kireev**

- Website: [bespredel.name](https://bespredel.name)
- Email: [hello@bespredel.name](mailto:hello@bespredel.name)
- GitHub: [@BespredeL](https://github.com/BespredeL)

---

## 🔗 Useful Links

- Project Website: [https://cvcounter.createdby.ru](https://cvcounter.createdby.ru)
- Documentation (Wiki EN): [docs/wiki.md](docs/wiki.md)
- Telemetry API Docs: [docs/telemetry_api.md](docs/telemetry_api.md)
- Inference Engines: [ONNX Runtime](https://onnxruntime.ai/) | [Intel OpenVINO](https://www.intel.com/openvino) | [Ultralytics YOLO](https://github.com/ultralytics) | [OpenCV](https://opencv.org/)

---

## 📄 License

This project is licensed under the open-source **[GNU AGPLv3](LICENSE)** license.

---

## ⭐ Support

If you find this project useful, please support it by giving a **star ⭐** on GitHub!