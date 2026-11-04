# CVCounter Multi-Architecture Object Detection Platform Guide

This document describes the multi-architecture Object Detection platform in CVCounter, providing comprehensive guides for inference, training, dataset management, and integrating diverse model families.

---

## 1. Detection Engine Architecture

CVCounter is decoupled from any single neural network library. The system is structured around an extensible Detection Engine:

```
                  ┌────────────────────────┐
                  │      CVCounter Core    │
                  │ (ObjectCounter / Loop) │
                  └───────────┬────────────┘
                              │
                    Unified `IDetector` API
              (predict, get_model_info, configure)
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
┌────────▼────────┐  ┌────────▼────────┐  ┌────────▼────────┐
│ Ultralytics YOLO│  │     RF-DETR     │  │      D-FINE     │ ... (RTMDet, ONNX)
│     Adapter     │  │     Adapter     │  │     Adapter     │
└────────┬────────┘  └────────┬────────┘  └────────┬────────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                              │
                     Inference Backends
          (PyTorch CUDA/CPU, ONNX Runtime, TensorRT)
```

### Core Contracts

- **`IDetector` (`system.detection.interface.IDetector`)**:
  - `load_model(weights: str | Path, **kwargs) -> None` / `load(...)`: Loads model checkpoint, initializes backend resources, and sets target device.
  - `unload() -> None` / `close()`: Releases GPU memory, cleans buffers, and resets loaded state.
  - `detect(image: np.ndarray, **kwargs) -> DetectionFrameResult` / `predict(...)`: Executes inference forward pass and returns standardized detection results.
  - `model_info() -> ModelInfo` / `get_model_info()`: Returns model architecture, variant, input size, active provider, and backend metadata.
  - `get_classes() -> dict[int, str]`: Returns mapping of class IDs to human-readable labels.
  - `configure(**kwargs) -> None`: Dynamically updates runtime parameters (confidence thresholds, IoU, etc.).
  - `warmup(input_size=None) -> None`: Pre-warms backend with dummy tensor to eliminate cold-start latency.
  - `is_loaded() -> bool`: Returns `True` when model weights are resident in memory.

- **`Detection` (`system.detection.result.Detection`)**:
  - Fields: `class_id: int`, `class_name: str`, `confidence: float`, `x1: float`, `y1: float`, `x2: float`, `y2: float`.
  - Coordinates are in pixel space matching original image dimensions and clamped: `0 <= x1 <= x2 <= width`, `0 <= y1 <= y2 <= height`.
  - Properties: `.width`, `.height`, `.area`, `.center` `(cx, cy)`, `.to_xyxy() -> [x1, y1, x2, y2]`.

- **`DetectionFrameResult` (`system.detection.result.DetectionFrameResult`)**:
  - `detections: list[Detection]`: List of individual detected objects in the frame.
  - Metadata: `model_name`, `model_version`, `inference_backend`, `inference_time` (seconds), `image_width`, `image_height`.
  - Properties: `.boxes_xyxy -> np.ndarray((N, 4))`, `.confidences -> np.ndarray((N,))`, `.classes -> np.ndarray((N,))`, `.inference_time_ms -> float`, `.is_empty -> bool`.
  - Methods:
    - `.to_tracker_array() -> np.ndarray((N, 6))`: Returns matrix of `[x1, y1, x2, y2, score, class_id]` directly consumed by the ByteTrack tracker.
    - `.to_legacy() -> tuple[np.ndarray, np.ndarray, np.ndarray]`: Returns `(boxes_xyxy, confidences, classes)` for legacy consumer compatibility.
    - `.filter_by_confidence(min_conf: float) -> DetectionFrameResult`: Returns filtered copy.
    - `.filter_by_classes(allowed_classes: Sequence[int | str]) -> DetectionFrameResult`: Returns class-filtered copy.
    - `.suppress_duplicates(iou_thresh: float) -> DetectionFrameResult`: Performs class-aware NMS deduplication.
    - `.clip_to_image(width, height) -> DetectionFrameResult`: Clamps all bounding boxes to image boundaries.

---

## 2. Supported Model Architectures

| Architecture | Model Variants | Default Backend | Licensing | Format |
| :--- | :--- | :--- | :--- | :--- |
| **Ultralytics YOLO** | YOLOv8 (n/s/m/l/x), YOLO11 (n/s/m/l/x), YOLO26 (n/s/m/l/x) | PyTorch / TensorRT / ONNX | AGPL-3.0 / Enterprise | `.pt`, `.engine`, `.onnx` |
| **Roboflow RF-DETR** | Nano, Small, Medium, Large | PyTorch / ONNX Runtime | Apache-2.0 (Core) | `.pth`, `.onnx` |
| **Peterande D-FINE** | Nano, Small, Medium, Large, XLarge | PyTorch / ONNX Runtime | Apache-2.0 | `.pth`, `.onnx` |
| **OpenMMLab RTMDet** | Tiny, Small, Medium, Large, Extra-Large | PyTorch (MMDet) / ONNX Runtime | Apache-2.0 | `.pth`, `.onnx` |
| **Generic ONNX** | Any exported model with YOLO or DETR head | ONNX Runtime (CPU/CUDA) | MIT / Permissive | `.onnx` |

---

## 3. Dependency Installation Profiles

To prevent version conflicts, dependencies are organized into modular installation profiles:

```bash
# 1. Base Core CVCounter (Zero AGPL, Web app, Database, Tracking):
pip install -r requirements.txt

# 2. Ultralytics YOLO models (.pt) and training:
pip install -r requirements-ultralytics.txt

# 3. Roboflow RF-DETR models (Apache-2.0):
pip install -r requirements-rfdetr.txt

# 4. Peterande D-FINE models (Apache-2.0):
pip install -r requirements-dfine.txt

# 5. OpenMMLab RTMDet models (Apache-2.0):
pip install -r requirements-rtmdet.txt
# (For MMDeploy / MMDetection: pip install openmim && mim install mmengine "mmcv>=2.0.0" mmdet)

# 6. ONNX Runtime acceleration:
pip install -r requirements-onnxruntime.txt

# 7. NVIDIA TensorRT acceleration:
pip install -r requirements-tensorrt.txt
```

---

## 4. CPU Inference

Every architecture supports CPU inference without requiring an NVIDIA GPU:

```python
from system.detection.registry import load_detector
import cv2

# Load YOLO on CPU
detector = load_detector("ultralytics", "weights/yolo26n.pt", device="cpu", confidence=0.4)

frame = cv2.imread("sample.jpg")
result = detector.predict(frame)

print(f"Detected {len(result)} objects in {result.inference_time_ms:.1f} ms on CPU")
detector.unload()
```

---

## 5. NVIDIA GPU Inference (CUDA)

When an NVIDIA GPU is available, pass `device="cuda"` or `device="cuda:0"`:

```python
import torch
from system.detection.registry import load_detector

if torch.cuda.is_available():
    name = torch.cuda.get_device_name(0)
    vram_mb = torch.cuda.get_device_properties(0).total_memory // (1024 * 1024)
    print(f"Running on {name} ({vram_mb} MB VRAM)")

# Load model on CUDA
detector = load_detector("ultralytics", "weights/yolo26n.pt", device="cuda:0", confidence=0.45)
result = detector.predict(frame)
print(f"CUDA inference latency: {result.inference_time_ms:.1f} ms")
detector.unload()
```

---

## 6. Pretrained Weights Loading

### RF-DETR
```python
from system.detection.registry import load_detector

# Automatically downloads/initializes pre-trained RF-DETR checkpoint
detector = load_detector("rf_detr", "models/rf_detr/rf_detr_small.pth", model_variant="small", device="cuda:0")
```

### D-FINE
```python
# Loads pre-trained D-FINE checkpoint (.pth)
detector = load_detector("d_fine", "models/dfine/dfine_s_coco.pth", model_variant="small", device="cuda:0")
```

### RTMDet
```python
# Loads RTMDet checkpoint with configuration
detector = load_detector(
    "rtmdet",
    "models/rtmdet/rtmdet_tiny_8xb32-300e_coco.pth",
    config_path="config/models/rtmdet/rtmdet_tiny_8xb32-300e_coco.py",
    device="cuda:0",
)
```

---

## 7. Training on Custom Datasets

The independent `TrainingEngine` (`system.training.engine.TrainingEngine`) trains models asynchronously in isolated threads, reporting metrics and checkpoints:

```python
from system.training.engine import TrainingEngine

engine = TrainingEngine()

job = engine.start_training(
    architecture="rf_detr",
    dataset_name="custom_dataset",
    dataset_root="storage/datasets/custom_dataset",
    classes=("target_a", "target_b"),
    epochs=50,
    batch_size=8,
    img_size=640,
    learning_rate=1e-4,
    device="cuda:0",
)

print(f"Job {job.job_id} launched. Current state: {job.state}")
```

Or via CLI:
```bash
python train.py train --config road-map --provider rf_detr --epochs 50 --export onnx
python train.py train --config road-map --provider d_fine --epochs 40 --export onnx
```

---

## 8. Fine-Tuning

To fine-tune existing weights on your domain-specific dataset:

```python
job = engine.start_training(
    architecture="d_fine",
    dataset_name="factory_cam",
    dataset_root="storage/datasets/factory_cam",
    classes=("part_ok", "part_defect"),
    pretrained_weights="models/dfine/dfine_s_coco.pth",
    epochs=25,
    batch_size=8,
    learning_rate=5e-5,
    device="cuda:0",
)
```

---

## 9. Resuming Interrupted Training

To resume training from the latest checkpoint (`last.pth`):

```python
job = engine.start_training(
    architecture="d_fine",
    dataset_name="factory_cam",
    dataset_root="storage/datasets/factory_cam",
    classes=("part_ok", "part_defect"),
    pretrained_weights="storage/runs/d_fine/factory_cam/weights/last.pth",
    epochs=50,
    device="cuda:0",
)
```

---

## 10. Dataset Management & Validation

CVCounter supports both **YOLO TXT** and **COCO JSON** datasets.

### Validation & Sequence Leakage Detection
```python
from system.datasets import DatasetValidator

validator = DatasetValidator(check_images_loadable=True)
report = validator.validate("storage/datasets/traffic_data")

print(f"Valid: {report.is_valid}")
print(f"Total Images: {report.total_images}, Total Annotations: {report.total_annotations}")
print(f"Data Leakage Detected: {report.leakage_detected}")
if report.leakage_detected:
    for leak in report.leakage_details:
        print(f"  [!] {leak}")
```

### Dataset Format Conversion
```python
from system.datasets import DatasetConverter

# Convert YOLO dataset to COCO format (non-destructive)
DatasetConverter.yolo_to_coco(
    yolo_root="storage/datasets/my_yolo_ds",
    output_dir="storage/datasets/my_coco_ds",
    classes=["person", "car"],
    copy_images=False,
)
```

---

## 11. ONNX Model Export

Export trained PyTorch checkpoints to deployable ONNX models:

```python
from system.detection.registry import load_detector

detector = load_detector("rf_detr", "storage/runs/rf_detr/my_run/weights/best.pth")
onnx_path = detector.export_onnx("models/rf_detr_exported.onnx", input_size=(640, 640))
print(f"Exported ONNX model saved to: {onnx_path}")
```

---

## 12. Inference via ONNX Runtime

Run any exported `.onnx` model with ONNX Runtime:

```python
from system.detection.registry import load_detector

# Runs via ONNX Runtime CPU or CUDA
detector = load_detector("onnx", "config/ultralytics/models/yolov8n.onnx", device="cuda:0")
result = detector.predict(frame)
print(f"ONNX Runtime detections: {len(result)}")
detector.unload()
```

---

## 13. NVIDIA TensorRT Inference

For high-throughput industrial deployments:

```python
from system.detection.registry import load_detector, is_tensorrt_available

if is_tensorrt_available():
    detector = load_detector(
        "ultralytics",
        "config/ultralytics/models/yolo11n.engine",
        device="cuda:0",
    )
    result = detector.predict(frame)
```

---

## 14. Model Metadata & Inspection

Centralized extraction of model classes, input contracts, and metadata from ONNX, PyTorch `.pt`, and sidecar files:

```python
from system.detection.metadata import get_model_metadata, extract_model_classes, load_model_manifest

# Extract full metadata from model weights
meta = get_model_metadata("config/ultralytics/models/yolo11n.onnx")
print("Format:", meta.get("format"))
print("Input size:", meta.get("input_size"))
print("Extracted classes count:", len(meta.get("classes", {})))

# Extract class dictionary directly
classes, source = extract_model_classes("config/ultralytics/models/yolo11n.onnx")
print(f"Loaded {len(classes)} classes from {source}")

# Load optional manifest sidecar if available
manifest = load_model_manifest("config/ultralytics/models/yolo11n.manifest.json")
if manifest:
    print("Architecture:", manifest.architecture)
    print("Decoder:", manifest.decoder)
```

---

## 15. Adding a New Object Detector

To add an object detector architecture to CVCounter:

1. Create adapter class in `system/detection/adapters/my_detector_adapter.py` inheriting `IDetector`.
2. Implement required methods: `load`, `unload`, `predict`, `get_model_info`, `get_classes`, `configure`, `is_loaded`.
3. In `predict()`, return a `DetectionFrameResult` containing normalized `Detection` objects.
4. Register the adapter in `system/detection/registry.py`:
   ```python
   register_detector("my_detector", lambda **kwargs: MyDetectorAdapter(**kwargs))
   ```
5. Done! The detector immediately works with `ObjectCounter`, `CounterLoop`, and `train.py`.

---

## 16. Troubleshooting & FAQ

- **`CUDA out of memory`**: Reduce `batch_size` during training or `input_size` during inference. Use `detector.unload()` to clear VRAM.
- **`Missing dependencies for architecture`**: Check which profile is needed and install the corresponding `requirements-<arch>.txt`.
- **`BBox out of bounds warnings`**: Verify your dataset with `DatasetValidator`. Coordinates in YOLO must be in `[0.0, 1.0]`.
- **`Data leakage warning`**: Ensure video frames from the same camera/recording are grouped together in either train or val, not split across both. Use `DatasetSplitter.split_items()`.

