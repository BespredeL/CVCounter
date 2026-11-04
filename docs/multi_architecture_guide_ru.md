# Руководство по мультиархитектурной платформе детекции CVCounter

Данный документ описывает мультиархитектурную платформу детекции объектов CVCounter и содержит подробные инструкции по инференсу, обучению, управлению датасетами и интеграции различных семейств нейросетевых моделей.

---

## 1. Архитектура движка детекции

CVCounter полностью отвязан от какой-либо одной библиотеки машинного обучения. Система построена на базе расширяемого движка детекции (Detection Engine):

```
                  ┌────────────────────────┐
                  │      CVCounter Core    │
                  │ (ObjectCounter / Loop) │
                  └───────────┬────────────┘
                              │
                    Единый API `IDetector`
              (detect, model_info, configure)
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
┌────────▼────────┐  ┌────────▼────────┐  ┌────────▼────────┐
│ Ultralytics YOLO│  │     RF-DETR     │  │      D-FINE     │ ... (RTMDet, ONNX)
│     Адаптер     │  │     Адаптер     │  │     Адаптер     │
└────────┬────────┘  └────────┬────────┘  └────────┬────────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                              │
                      Бэкенды инференса
          (PyTorch CUDA/CPU, ONNX Runtime, TensorRT)
```

### Базовые контракты

- **`IDetector` (`system.detection.interface.IDetector`)**:
  - `load_model(weights: str | Path, **kwargs) -> None` / `load(...)`: загрузка контрольной точки модели, инициализация ресурсов бэкенда и выбор целевого устройства.
  - `unload() -> None` / `close()`: освобождение памяти GPU/VRAM, очистка буферов и сброс состояния загрузки.
  - `detect(image: np.ndarray, **kwargs) -> DetectionFrameResult` / `predict(...)`: выполнение прямого прохода инференса и возврат стандартизированного результата детекции.
  - `model_info() -> ModelInfo` / `get_model_info()`: получение информации об архитектуре, варианте, размере входа, активном провайдере и метаданных бэкенда.
  - `get_classes() -> dict[int, str]`: получение словаря соответствия ID классов их названиям.
  - `configure(**kwargs) -> None`: динамическое обновление параметров инференса (пороги confidence, IoU и др.).
  - `warmup(input_size=None) -> None`: предварительный прогрев модели фиктивным тензором для устранения задержек первого кадра.
  - `is_loaded() -> bool`: возвращает `True`, если веса модели загружены в память.

- **`Detection` (`system.detection.result.Detection`)**:
  - Поля: `class_id: int`, `class_name: str`, `confidence: float`, `x1: float`, `y1: float`, `x2: float`, `y2: float`.
  - Координаты нормализованы в пиксельное пространство исходного изображения и ограничены его границами: `0 <= x1 <= x2 <= width`, `0 <= y1 <= y2 <= height`.
  - Свойства: `.width`, `.height`, `.area`, `.center` `(cx, cy)`, `.to_xyxy() -> [x1, y1, x2, y2]`.

- **`DetectionFrameResult` (`system.detection.result.DetectionFrameResult`)**:
  - `detections: list[Detection]`: список объектов детекции на кадре.
  - Метаданные: `model_name`, `model_version`, `inference_backend`, `inference_time` (в секундах), `image_width`, `image_height`.
  - Свойства: `.boxes_xyxy -> np.ndarray((N, 4))`, `.confidences -> np.ndarray((N,))`, `.classes -> np.ndarray((N,))`, `.inference_time_ms -> float`, `.is_empty -> bool`.
  - Методы:
    - `.to_tracker_array() -> np.ndarray((N, 6))`: возвращает матрицу строк `[x1, y1, x2, y2, score, class_id]` для прямой передачи в трекер ByteTrack.
    - `.to_legacy() -> tuple[np.ndarray, np.ndarray, np.ndarray]`: возвращает кортеж `(boxes_xyxy, confidences, classes)` для обратной совместимости.
    - `.filter_by_confidence(min_conf: float) -> DetectionFrameResult`: фильтрация детекций по минимальной уверенности.
    - `.filter_by_classes(allowed_classes: Sequence[int | str]) -> DetectionFrameResult`: фильтрация детекций по списку разрешённых классов.
    - `.suppress_duplicates(iou_thresh: float) -> DetectionFrameResult`: подавление дубликатов детекций с учётом классов (NMS).
    - `.clip_to_image(width, height) -> DetectionFrameResult`: обрезка координат боксов по границам изображения.

---

## 2. Поддерживаемые архитектуры моделей

| Архитектура | Варианты моделей | Бэкенд по умолчанию | Лицензия | Форматы |
| :--- | :--- | :--- | :--- | :--- |
| **Ultralytics YOLO** | YOLOv8 (n/s/m/l/x), YOLO11 (n/s/m/l/x), YOLO26 (n/s/m/l/x) | PyTorch / TensorRT / ONNX | AGPL-3.0 / Enterprise | `.pt`, `.engine`, `.onnx` |
| **Roboflow RF-DETR** | Nano, Small, Medium, Large | PyTorch / ONNX Runtime | Apache-2.0 (Core) | `.pth`, `.onnx` |
| **Peterande D-FINE** | Nano, Small, Medium, Large, XLarge | PyTorch / ONNX Runtime | Apache-2.0 | `.pth`, `.onnx` |
| **OpenMMLab RTMDet** | Tiny, Small, Medium, Large, Extra-Large | PyTorch (MMDet) / ONNX Runtime | Apache-2.0 | `.pth`, `.onnx` |
| **Generic ONNX** | Любые экспортированные модели с головами YOLO, DETR или RTMDet | ONNX Runtime (CPU/CUDA) | MIT / Permissive | `.onnx` |

---

## 3. Профили установки зависимостей

Для предотвращения конфликтов версий библиотеки разделены на модульные профили установки:

```bash
# 1. Базовый Core CVCounter (Zero AGPL, веб-приложение, БД, трекинг):
pip install -r requirements.txt

# 2. Модели Ultralytics YOLO (.pt) и обучение:
pip install -r requirements-ultralytics.txt

# 3. Модели Roboflow RF-DETR (Apache-2.0):
pip install -r requirements-rfdetr.txt

# 4. Модели Peterande D-FINE (Apache-2.0):
pip install -r requirements-dfine.txt

# 5. Модели OpenMMLab RTMDet (Apache-2.0):
pip install -r requirements-rtmdet.txt
# (Для сборки MMDeploy / MMDetection: pip install openmim && mim install mmengine "mmcv>=2.0.0" mmdet)

# 6. Ускорение через ONNX Runtime:
pip install -r requirements-onnxruntime.txt

# 7. Аппаратное ускорение Intel OpenVINO:
pip install -r requirements-openvino.txt

# 8. Ускорение NVIDIA TensorRT:
pip install -r requirements-tensorrt.txt
```

---

## 4. Инференс на CPU

Каждая архитектура поддерживает инференс на центральном процессоре без необходимости наличия дискретной видеокарты NVIDIA:

```python
import cv2
from system.detection.registry import load_detector

# Загрузка модели YOLO на CPU
detector = load_detector("ultralytics", "config/ultralytics/models/yolo11n.pt", device="cpu", confidence=0.4)

frame = cv2.imread("sample.jpg")
result = detector.detect(frame)

print(f"Обнаружено {len(result)} объектов за {result.inference_time_ms:.1f} мс на CPU")
detector.unload()
```

---

## 5. Инференс на NVIDIA GPU (CUDA)

При наличии дискретной видеокарты NVIDIA укажите `device="cuda"` или `device="cuda:0"`:

```python
import torch
from system.detection.registry import load_detector

if torch.cuda.is_available():
    name = torch.cuda.get_device_name(0)
    vram_mb = torch.cuda.get_device_properties(0).total_memory // (1024 * 1024)
    print(f"Запуск на {name} ({vram_mb} МБ VRAM)")

# Загрузка модели на CUDA
detector = load_detector("ultralytics", "config/ultralytics/models/yolo11n.pt", device="cuda:0", confidence=0.45)
result = detector.detect(frame)
print(f"Задержка инференса CUDA: {result.inference_time_ms:.1f} мс")
detector.unload()
```

---

## 6. Загрузка предобученных весов

### RF-DETR
```python
from system.detection.registry import load_detector

# Загрузка контрольной точки RF-DETR
detector = load_detector("rf_detr", "models/rf_detr/rf_detr_small.pth", model_variant="small", device="cuda:0")
```

### D-FINE
```python
# Загрузка контрольной точки D-FINE (.pth)
detector = load_detector("d_fine", "models/dfine/dfine_s_coco.pth", model_variant="small", device="cuda:0")
```

### RTMDet
```python
# Загрузка контрольной точки RTMDet с файлом конфигурации
detector = load_detector(
    "rtmdet",
    "models/rtmdet/rtmdet_tiny_8xb32-300e_coco.pth",
    config_path="config/models/rtmdet/rtmdet_tiny_8xb32-300e_coco.py",
    device="cuda:0",
)
```

---

## 7. Обучение на пользовательских датасетах

Модуль `TrainingEngine` (`system.training.engine.TrainingEngine`) выполняет обучение моделей асинхронно в изолированных потоках, публикуя метрики и промежуточные контрольные точки:

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

print(f"Задача {job.job_id} запущена. Текущее состояние: {job.state}")
```

Либо через CLI:
```bash
python train.py train --config road-map --provider rf_detr --epochs 50 --export onnx
python train.py train --config road-map --provider d_fine --epochs 40 --export onnx
```

---

## 8. Дообучение (Fine-Tuning)

Для дообучения существующих весов на специализированном датасете:

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

## 9. Возобновление прерванного обучения

Для возобновления обучения с последней контрольной точки (`last.pth`):

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

## 10. Управление датасетами и валидация

CVCounter поддерживает форматы датасетов **YOLO TXT** и **COCO JSON**.

### Валидация датасета и проверка утечек последовательностей (Data Leakage)
```python
from system.datasets import DatasetValidator

validator = DatasetValidator(check_images_loadable=True)
report = validator.validate("storage/datasets/traffic_data")

print(f"Датасет корректен: {report.is_valid}")
print(f"Изображений: {report.total_images}, Размеченных объектов: {report.total_annotations}")
print(f"Обнаружена утечка кадров: {report.leakage_detected}")
if report.leakage_detected:
    for leak in report.leakage_details:
        print(f"  [!] {leak}")
```

### Конвертация форматов датасета
```python
from system.datasets import DatasetConverter

# Конвертация датасета из YOLO в формат COCO (без изменения исходных файлов)
DatasetConverter.yolo_to_coco(
    yolo_root="storage/datasets/my_yolo_ds",
    output_dir="storage/datasets/my_coco_ds",
    classes=["person", "car"],
    copy_images=False,
)
```

---

## 11. Экспорт моделей в формат ONNX

Экспорт обученных контрольных точек PyTorch в формат ONNX для последующего промышленного деплоя:

```python
from system.detection.registry import load_detector

detector = load_detector("rf_detr", "storage/runs/rf_detr/my_run/weights/best.pth")
onnx_path = detector.export_onnx("models/rf_detr_exported.onnx", input_size=(640, 640))
print(f"Экспортированная модель сохранена в: {onnx_path}")
```

---

## 12. Инференс через ONNX Runtime

Запуск экспортированных моделей `.onnx` через ONNX Runtime:

```python
from system.detection.registry import load_detector

# Запуск через ONNX Runtime (CPU, CUDA или OpenVINO)
detector = load_detector("onnx", "config/ultralytics/models/yolo11n.onnx", device="cuda:0")
result = detector.detect(frame)
print(f"Детекций ONNX Runtime: {len(result)}")
detector.unload()
```

---

## 13. Инференс на NVIDIA TensorRT

Для максимальной производительности в промышленных задачах:

```python
from system.detection.registry import load_detector, is_tensorrt_available

if is_tensorrt_available():
    detector = load_detector(
        "ultralytics",
        "config/ultralytics/models/yolo11n.engine",
        device="cuda:0",
    )
    result = detector.detect(frame)
```

---

## 14. Метаданные моделей и инспекция

Централизованное извлечение классов, входных контрактов и метаданных из файлов ONNX, PyTorch `.pt` и файлов-манифестов:

```python
from system.detection.metadata import get_model_metadata, extract_model_classes, load_model_manifest

# Полное извлечение метаданных из весов модели
meta = get_model_metadata("config/ultralytics/models/yolo11n.onnx")
print("Формат:", meta.get("format"))
print("Размер входа:", meta.get("input_size"))
print("Количество классов:", len(meta.get("classes", {})))

# Прямое извлечение словаря классов
classes, source = extract_model_classes("config/ultralytics/models/yolo11n.onnx")
print(f"Загружено {len(classes)} классов из источника {source}")

# Загрузка опционального манифеста модели
manifest = load_model_manifest("config/ultralytics/models/yolo11n.manifest.json")
if manifest:
    print("Архитектура:", manifest.architecture)
    print("Декодер:", manifest.decoder)
```

---

## 15. Добавление новой архитектуры детектора

Для добавления новой архитектуры детекции в CVCounter:

1. Создайте класс-адаптер в `system/detection/adapters/my_detector_adapter.py`, наследующий `IDetector`.
2. Реализуйте обязательные методы: `load_model`, `unload`, `detect` (или `predict`), `model_info`, `get_classes`, `configure`, `is_loaded`.
3. В методе `detect()` возвращайте объект `DetectionFrameResult`, содержащий список объектов `Detection`.
4. Зарегистрируйте адаптер в реестре `system/detection/registry.py`:
   ```python
   register_detector("my_detector", lambda **kwargs: MyDetectorAdapter(**kwargs))
   ```
5. Готово! Детектор мгновенно становится доступен для `ObjectCounter`, видеопотоков `CounterLoop` и CLI-инструмента `train.py`.

---

## 16. Устранение неполадок и частые вопросы (FAQ)

- **`CUDA out of memory`**: Уменьшите `batch_size` при обучении или `input_size` при инференсе. Используйте `detector.unload()` для своевременного освобождения видеопамяти.
- **`Missing dependencies for architecture`**: Проверьте требуемый профиль оборудования и установите соответствующий файл `requirements-<arch>.txt`.
- **`BBox out of bounds warnings`**: Проверьте датасет валидатором `DatasetValidator`. Координаты в YOLO-разметке должны находиться строго в диапазоне `[0.0, 1.0]`.
- **`Data leakage warning`**: Убедитесь, что последовательные кадры из одной видеозаписи сгруппированы целиком либо в `train`, либо в `val`, а не перемешаны случайным образом. Используйте `DatasetSplitter.split_items()`.

