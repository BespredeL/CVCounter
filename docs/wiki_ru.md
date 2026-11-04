# CVCounter — Документация (Wiki)

[![Website](https://img.shields.io/badge/website-cvcounter.createdby.ru-4dabf7.svg)](https://cvcounter.createdby.ru)
[![Author](https://img.shields.io/badge/author-bespredel.name-8a2be2.svg)](https://bespredel.name)
[![Wiki RU](https://img.shields.io/badge/Wiki-RU-blue.svg)](wiki_ru.md)
[![Wiki EN](https://img.shields.io/badge/Wiki-EN-blue.svg)](wiki.md)
[![License](https://img.shields.io/badge/license-AGPL--3.0-458a7b.svg)](https://github.com/BespredeL/CVCounter/blob/master/LICENSE)

Добро пожаловать в полную техническую документацию системы компьютерного зрения **CVCounter**!

---

## 📑 Содержание

1. [Описание и возможности](#-описание-и-возможности)
2. [Архитектура приложения](#-архитектура-приложения)
3. [Установка и запуск](#-установка-и-запуск)
4. [Системы детекции и инференс](#-системы-детекции-и-инференс)
5. [Полный справочник конфигурации (`config.json`)](#-полный-справочник-конфигурации-configjson)
6. [Веб-интерфейс и режимы работы](#-веб-интерфейс-и-режимы-работы)
7. [Датасеты, разметка и обучение](#-датасеты-разметка-и-обучение)
8. [Справочник REST API](#-справочник-rest-api)
9. [Аутентификация и сессии](#-аутентификация-и-сессии)
10. [Real-time события (Socket.IO)](#-real-time-события-socketio)
11. [Часто задаваемые вопросы (FAQ)](#-часто-задаваемые-вопросы-faq)
12. [Вклад в проект и лицензия](#-вклад-в-проект-и-лицензия)

---

## 🧠 Описание и возможности

**CVCounter** — это законченная масштабируемая система компьютерного зрения для детекции, трекинга и подсчёта объектов в реальном времени. Система работает как локальный веб-сервис на базе Flask и не требует установки дополнительного ПО на клиентские устройства: операторы работают через любой современный браузер (ПК, планшеты, сенсорные терминалы).

### Ключевые возможности:

- 🎯 **Мульти-зонный подсчёт:** визуальный редактор полигональных зон (произвольное количество зон у каждого детектора, индивидуальные цвета, подсчёт по объединению масок).
- 🔄 **Высокоточный трекинг:** устойчивое отслеживание объектов между кадрами с предотвращением повторного подсчёта.
- 🏷️ **Разбивка по классам:** подсчёт суммарного количества и количества в текущей партии по каждому обнаруженному классу.
- 🎥 **Гибкие источники видео:** RTSP/RTMP-потоки IP-камер, локальные веб-камеры (USB/V4L2) и видеофайлы.
- 🎬 **Умная видеозапись:** автоматический старт записи видео при появлении детекций и остановка по настраиваемому таймауту неактивности (`idle_timeout`).
- 🧠 **Поддержка любых моделей:** автоматический выбор или явное указание архитектуры и рантайма (Ultralytics YOLO, ONNX Runtime, RF-DETR, D-FINE, RTMDet).
- 📚 **Полный цикл работы с датасетами:** сбор кадров из потока, разметка боксов/полигонов, активное обучение (Active Learning), авторазметка, выгрузка в YOLO и COCO, обучение через подключаемые provider-ы (Ultralytics YOLO, torchvision) и применение обученных весов в 1 клик.
- 📊 **Отчёты и аналитика:** журнал сессий с разбивкой по партиям, брак/коррекция, просмотр сохранённых кадров и видео, печать и экспорт в A4 PDF.
- 🚀 **1-Click установщик:** скрипт `install.bat` / `install.sh` автоматически распознаёт модель GPU (NVIDIA CUDA, AMD DirectML, Intel Arc / OpenVINO) и собирает готовое окружение.
- 🛠️ **Управление рантаймами (AI Runtimes Center):** проверка статуса CUDA, TensorRT, OpenVINO и доустановка библиотек через веб-интерфейс.
- 🔐 **Безопасность:** авторизация администратора, защита настроек и датасетов, шифрование паролей scrypt.

---

## 🏛️ Архитектура приложения

CVCounter построен по модульной слоистой архитектуре с чётким разделением ответственности между захватом видео, инференсом, трекингом, подсчётом, веб-интерфейсом и фоновыми задачами.

### Схема обработки видеокадра и данных:

```mermaid
flowchart TD
    A[Видеоисточник<br>RTSP / WebCam / File] --> B[VideoStreamManager / VideoCapture]
    B --> C[CounterLoop<br>Фоновый поток обработки]
    C --> D[IDetector<br>YOLO / ONNX / DETR / DFINE / RTMDet]
    D -->|DetectionFrameResult| E[ByteTracker<br>Трекинг и привязка Track ID]
    E --> F[CountKernel<br>Проверка пересечения зон и полигонов]
    F --> G[CountState<br>Счётчики, классы, партии, брак]
    G --> H[FrameRenderer<br>Отрисовка боксов, зон и меток]
    H --> I[MJPEG Streamer<br>Видео в браузер оператора]
    G --> J[DatabaseManager<br>Сохранение отчётов в SQLite/MySQL]
    G --> K[Socket.IO Server<br>Real-time телеметрия на дашборд]
    C --> L[RecordingControl<br>Запись событийных видеороликов]
```

### Структура проекта:

```
CVCounter/
├── app.py                      # Точка входа, запуск веб-сервера и сокетов
├── train.py                    # Автономный CLI обучения и экспорта моделей
├── install.py                  # Кроссплатформенный установщик с автоопределением оборудования
├── config/                     # Конфигурационные файлы, веса моделей и база данных
│   ├── config.json             # Рабочий файл конфигурации системы
│   ├── config.example.json     # Эталонный файл настроек
│   ├── database.sqlite         # База данных SQLite (сессии, отчёты, брак)
│   ├── ultralytics/            # Конфигурации и веса моделей Ultralytics YOLO
│   └── torchvision/            # Конфигурации и базовые чекпойнты torchvision
├── routes/                     # Модули представлений (Flask Blueprints)
│   ├── main.py                 # Дашборд, авторизация (/login, /logout), справка
│   ├── counters.py             # Экраны счётчиков, видеопотоки MJPEG, редактор зон
│   ├── reports.py              # Просмотр истории сессий, медиафайлы, экспорт в A4 PDF
│   ├── datasets.py             # Сбор кадров, разметка, обучение и авторазметка
│   ├── settings/               # Модульный пакет настроек (камеры, модели, рантаймы, логи, API-ключи)
│   └── api/                    # REST API v1 (/api/v1/counters, /api/v1/reports, /api/v1/system)
├── system/                     # Внутреннее ядро системы
│   ├── app_factory.py          # Application Factory (сборка Flask-приложения и Socket.IO)
│   ├── runtime.py              # AppRuntime (контейнер синглтонов и рантайм-состояния)
│   ├── auth/                   # Аутентификация, валидация сессий и API-ключей, хэширование scrypt
│   ├── core/                   # Пайплайн обработки: ObjectCounter, CounterLoop, ByteTrack, FrameRenderer
│   ├── db/                     # Модели ORM SQLAlchemy, миграции и репозитории
│   ├── detection/              # Единая подсистема детекции: IDetector, адаптеры, transforms, postproc, registry
│   ├── managers/               # Менеджеры видеопотоков, тредов, базы данных, уведомлений, задач обучения
│   ├── services/               # Сервисный слой: состояние счётчиков, события, хранилище результатов
│   ├── datasets/               # Сервис датасетов, валидация утечек, конвертация YOLO/COCO
│   ├── training/               # TrainingEngine, реестр провайдеров (Ultralytics, torchvision), экспорт
│   └── utils/                  # I18n, телеметрия, валидаторы, логгер, детектор видеокарт
├── static/                     # Статические ресурсы (CSS, JS, шрифты, иконки)
├── templates/                  # Шаблоны страниц Jinja2
└── storage/                    # Постоянное хранилище (логи, кадры, записи, датасеты)
```

### Основные Blueprints:

| Blueprint | Модуль / Пакет | Префикс URL | Назначение |
|---|---|---|---|
| `main` | `routes/main.py` | `/` | Дашборд, авторизация (`/login`, `/logout`), справочные страницы (`/page/help`) |
| `counters` | `routes/counters.py` | `/` | Экраны счётчиков, видео MJPEG, редактор зон, сохранение партий |
| `reports` | `routes/reports.py` | `/reports` | История сессий, сохранённые кадры/видео, печатные формы A4 |
| `datasets` | `routes/datasets.py` | `/datasets` | Подготовка данных, разметка, обучение моделей (*auth*) |
| `settings` | `routes/settings/` | `/settings`, `/system_info` | Конфигурация камер, рантаймы, системный статус, логи, модели (*auth*) |
| `api_v1` | `routes/api/v1/` | `/api/v1` | Программный REST API v1: счётчики, отчёты, системное здоровье |

---

## 📦 Установка и запуск

### Способ 1: Автоматическая установка в 1 клик (Рекомендуется)

Установщик `install.py` определяет аппаратный профиль, устанавливает только Core-зависимости и создаёт конфигурацию. ML runtime-ы и PyTorch/Ultralytics устанавливаются только по явному запросу:

- **Windows:** дважды кликните на `install.bat`. Для запуска используйте `start.bat`.
- **Linux / macOS:**
  ```bash
  chmod +x install.sh start.sh
  ./install.sh
  ./start.sh
  ```

#### Поддерживаемые профили оборудования:
- **`nvidia_cuda`:** Целевой профиль для NVIDIA; `--with-inference` устанавливает `onnxruntime-gpu`, `--with-pytorch` — подходящую сборку PyTorch.
- **`amd_directml`:** Целевой профиль AMD; `--with-inference` устанавливает ONNX Runtime DirectML.
- **`intel_openvino`:** Целевой профиль Intel; `--with-inference` устанавливает OpenVINO и ONNX Runtime.
- **`cpu`:** Целевой CPU-профиль; `--with-inference` устанавливает ONNX Runtime CPU.

Флаги установщика:
```bash
python install.py --profile nvidia_cuda  # Принудительный выбор профиля
python install.py --with-inference       # Установка runtime инференса для выбранного профиля
python install.py --with-ultralytics     # PyTorch + Ultralytics (.pt и обучение YOLO)
python install.py --with-pytorch         # Только PyTorch provider
python install.py --provider onnxruntime --provider openvino  # Несколько встроенных runtime
python install.py --provider opencv       # OpenCV DNN уже входит в Core; пакет не нужен
python install.py --reinstall            # Переустановка всех пакетов
python install.py --no-color             # Отключение ANSI-цветов
```

`--provider` принимает `onnxruntime`, `openvino`, `opencv`, `pytorch` или
`ultralytics`; флаг можно повторять. Старый `--with-inference` сохранён и
устанавливает комбинацию runtime-ов для обнаруженного или заданного профиля.

---

### Способ 2: Ручная установка

1. Клонируйте проект:
   ```bash
   git clone https://github.com/BespredeL/CVCounter.git
   cd CVCounter
   ```
2. Создайте и активируйте виртуальное окружение:
   ```bash
   # Linux/macOS:
   python3 -m venv venv
   source venv/bin/activate

   # Windows:
   python -m venv venv
   .\venv\Scripts\activate
   ```
3. Установите зависимости:
   ```bash
   pip install -r requirements.txt

   # Опционально: ONNX Runtime CPU inference
   pip install -r requirements-onnxruntime.txt
   
   # Опционально: для обучения YOLO и моделей .pt
   pip install -r requirements-ultralytics.txt

   # Опционально: для ускорения Intel OpenVINO
   pip install -r requirements-openvino.txt

   # Опционально: инструменты ONNX export/optimization
   pip install -r requirements-onnx-export.txt
   ```
4. Создайте рабочий конфигурационный файл:
   ```bash
   cp config/config.example.json config/config.json
   ```
5. Запустите приложение:
   ```bash
   python app.py
   ```
   Откройте в браузере: `http://localhost:8080`. Данные для входа по умолчанию: `admin` / `admin`.

---

### Способ 3: Развертывание в Docker

```bash
docker-compose up --build
```
Файлы конфигурации и хранилище примонтированы через тома Docker (`config/` и `storage/`).

---

## 🧠 Системы детекции и инференс

Единая подсистема детекции (`system/detection/`) предоставляет унифицированный интерфейс `IDetector` (`system/detection/interface.py`) и фабрику `load_detector` (`system/detection/registry.py`). Подсистема полностью изолирует работу с моделями различных архитектур (Ultralytics YOLO, Generic ONNX, RF-DETR, D-FINE, RTMDet) от видеопайплайна.

Каждый детектор возвращает структурированный `DetectionFrameResult`, содержащий список объектов `Detection` и метод `.to_tracker_array() -> np.ndarray(N, 6)` с форматом строк `[x1, y1, x2, y2, score, class_id]` для передачи в трекер ByteTrack.

> Подробное руководство по работе с мультиархитектурной платформой, инференсу на CPU/CUDA, обучению и экспорту см. в [Руководстве по мультиархитектурной платформе](multi_architecture_guide_ru.md).

### Необязательный манифест модели

Рядом с моделью можно разместить необязательный файл `<имя-модели>.manifest.json`. Он описывает модель, не предполагая, что расширение файла определяет её архитектуру или формат выходных данных:

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

Preprocessing, входной тензор, выход и decoder описываются отдельно: загрузки артефакта runtime недостаточно, чтобы считать модель совместимой. Модуль постпроцессинга (`system/detection/postprocessing.py`) поддерживает декодеры `yolo_outputs` (матрицы по якорям и end-to-end тензоры `[N, 6]`), `detr_outputs` (пары логитов классов и нормализованных боксов для DETR/RF-DETR/D-FINE) и `rtmdet_outputs`. Для ONNX-моделей используется единый канонический бэкенд ONNX Runtime (`system/detection/backends/onnx_session.py`) с динамическим выбором Execution Provider (CUDA, OpenVINO, DirectML, CPU).

### Поддерживаемые значения `model_type`:

| `model_type` | Архитектура / Движок | Лицензия | Поддерживаемые форматы | Рекомендуемое применение |
|---|---|---|---|---|
| **`auto`** | Автоопределение | — | `.onnx`, `.pt`, `.engine`, `.pth` | **По умолчанию.** Автоматически определяет архитектуру по имени файла и расширению |
| **`yolo`**, `ultralytics` | [Ultralytics YOLO](https://github.com/ultralytics/ultralytics) | AGPL-3.0 | `.pt`, `.engine` (TensorRT) | YOLOv8–YOLO26, нативный PyTorch, TensorRT Engine, обучение моделей |
| **`onnx`**, `onnxruntime` | [ONNX Runtime](https://onnxruntime.ai/) | MIT | `.onnx` (YOLO, DETR, RTMDet) | Кроссплатформенный инференс с максимальной скоростью (CUDA, DirectML, OpenVINO, CPU) |
| **`rf_detr`** | [Roboflow RF-DETR](https://github.com/roboflow/rf-detr) | Apache-2.0 | `.pth`, `.pt`, `.onnx` | Трансформерные детекторы RF-DETR (Nano, Small, Medium, Large) |
| **`d_fine`** | [Peterande D-FINE](https://github.com/Peterande/D-FINE) | Apache-2.0 | `.pth`, `.pt`, `.onnx` | Real-time DETR с распределением регрессии границ (N/S/M/L/X) |
| **`rtmdet`** | [OpenMMLab RTMDet](https://github.com/open-mmlab/mmdetection) | Apache-2.0 | `.pth`, `.onnx` | Высокоскоростные детекторы OpenMMLab RTMDet (Tiny, S, M, L, X) |

### Примеры конфигурации детектора

**Автоматический выбор (рекомендуется):**
```json
{
  "model_type": "auto",
  "weights_path": "config/ultralytics/models/yolo11n.onnx"
}
```

**ONNX Runtime с аппаратными провайдерами (CUDA):**
```json
{
  "model_type": "onnx",
  "weights_path": "config/ultralytics/models/yolo11n.onnx",
  "input_size": 640,
  "providers": ["CUDAExecutionProvider", "CPUExecutionProvider"]
}
```

**ONNX Runtime с OpenVINO Execution Provider (для процессоров Intel, iGPU и видеокарт Arc):**
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

### Добавление собственного детектора

1. Создайте класс-наследник `IDetector`:
   ```python
   import numpy as np
   from system.detection import IDetector, DetectionFrameResult, Detection, register_detector

   class CustomDetector(IDetector):
       def __init__(self, weights: str, **kwargs):
           self.weights = weights
           # Инициализация модели

       def is_loaded(self) -> bool:
           return True

       def unload(self) -> None:
           pass

       def detect(self, frame: np.ndarray) -> DetectionFrameResult:
           # Инференс и формирование результатов
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

   # Регистрация фабрики детектора в реестре
   register_detector("custom_detector", lambda **kwargs: CustomDetector(**kwargs))
   ```
2. Укажите `"model_type": "custom_detector"` в конфигурации камеры.

---

## ⚙️ Полный справочник конфигурации (`config.json`)

Файл конфигурации разделен на логические секции:

### 1. `general` — Общие параметры системы

| Параметр | Описание | По умолчанию |
|---|---|---|
| `debug` | Режим отладки Flask | `true` |
| `system_check` | Вывод доступных GPU/runtime и статуса optional PyTorch при запуске | `true` |
| `log_path` | Путь к файлу логов приложения | `"storage/logs/cvcounter.log"` |
| `log_level` | Минимальный уровень логирования (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `"INFO"` |
| `log_console` | Дублирование логов в стандартный вывод консоли | `false` |
| `default_language` | Язык интерфейса по умолчанию (`"ru"`, `"en"`) | `"ru"` |
| `allow_unsafe_werkzeug` | Разрешение запуска Werkzeug в production-окружениях | `true` |
| `button_change_theme` | Отображение кнопки переключения светлой/тёмной темы | `true` |
| `button_fullscreen` | Отображение кнопки перехода в полноэкранный режим | `true` |
| `button_backward` | Отображение кнопки возврата назад в интерфейсе | `false` |
| `button_save_capture` | Отображение кнопки ручного сохранения кадра | `false` |
| `collapsed_keyboard` | Отображение экранной клавиатуры свёрнутой | `true` |

### 2. `server` — Параметры веб-сервера

| Параметр | Описание | По умолчанию |
|---|---|---|
| `host` | Сетевой интерфейс для прослушивания (`"0.0.0.0"` — все интерфейсы) | `"0.0.0.0"` |
| `port` | TCP-порт веб-сервера | `8080` |
| `use_reloader` | Автоперезапуск сервера при изменении исходного кода | `false` |
| `log_output` | Логирование входящих HTTP-запросов | `false` |
| `secret_key` | Секретный ключ Flask-сессий (автогенерация при пустом значении) | `""` |
| `allowed_origins` | CORS-политика источников Socket.IO | `"*"` |
| `socketio_async_mode` | Режим асинхронности Socket.IO (`"threading"`, `"eventlet"`, `"gevent"`) | `"threading"` |
| `socketio_transports` | Разрешённые транспорты Socket.IO | `["polling", "websocket"]` |
| `socketio_upgrade` | Разрешение апгрейда с HTTP polling до WebSocket | `true` |
| `allow_web_control` | Разрешение перезапуска и остановки сервера через веб-интерфейс | `true` |

### 3. `datasets` — Параметры датасетов

| Параметр | Описание | По умолчанию |
|---|---|---|
| `max_upload_mb` | Максимальный размер загружаемого ZIP-архива с изображениями (МБ) | `512` |

### 4. `users` — Учётные записи

Пароли хранятся в виде scrypt-хэшей. Учётная запись администратора по умолчанию:
```json
"users": {
    "admin": "scrypt:32768:8:1$rsdPYhqaQqpXQQ0o$aa3359c86228b4cee5fe8c4ed694db4b371fa7fab5100fa7b446db7e1ed8077e3bb63228d4a1899aeeef9b8d15f8e8bdbcc3457f020bcb3ec320332c76b5896b"
}
```
*(Пароль по умолчанию: `admin`)*.

### 5. `db` — База данных

| Параметр | Описание | По умолчанию |
|---|---|---|
| `uri` | Строка подключения SQLAlchemy | `"sqlite:///config/database.sqlite"` |
| `prefix` | Префикс таблиц базы данных | `""` |

### 6. `telemetry` — Диагностика и телеметрия

| Параметр | Описание | По умолчанию |
|---|---|---|
| `enabled` | Автоматическая фоновая отправка данных об ошибках | `true` |
| `endpoint` | HTTPS-эндпоинт приёмника телеметрии | `"https://bespredel.name/api/cvcounter/telemetry"` |
| `send_errors` | Отправка неперехваченных исключений | `true` |
| `send_usage` | Отправка событий использования; ярлыки камер уходят как стабильные псевдонимы | `true` |
| `flush_interval_sec`| Интервал фонового сброса очереди (секунды) | `3600` |
| `max_batch_size` | Максимум событий в HTTP-запросе; раньше сбрасывает буфер при заполнении | `200` |
| `max_queue_size` | Максимальный размер очереди событий в памяти | `400` |
| `error_dedup_sec` | Окно подавления одинаковых сообщений об ошибках (секунды) | `600` |
| `timeout_sec` | HTTP-таймаут запроса телеметрии | `10` |
| `hmac_secret` | Секретный ключ подписи заголовка `X-CVCounter-Signature` | `""` |
| `compress` | Сжатие батчей телеметрии gzip | `true` |

### 7. `form` — Пользовательские поля формы подсчёта

Секция определяет динамические поля для ввода данных о партии (наименование, номер партии, оператор и т.д.):
- `defect_show`: показ формы ввода количества брака (`true`/`false`).
- `correct_show`: показ формы ручной коррекции счёта (`true`/`false`).
- `custom_fields`: словарь полей. Поддерживаемые типы: `text`, `number`, `textarea`, `date`, `datetime-local`, `select` (с массивом `options`).

### 8. `detection_default` и `detections.<location>`

Все камеры в секции `detections` наследуют значения из `detection_default`, если они не переопределены:

| Параметр | Описание | Пример |
|---|---|---|
| `label` | Отображаемое название камеры | `"Линия упаковки 1"` |
| `video_path` | URL RTSP-потока, путь к файлу или индекс веб-камеры (`0`, `1`) | `"rtsp://admin:12345@192.168.1.10:554/ch1"` |
| `start_total_count` | Начальное значение общего счётчика | `0` |
| `model_type` | Тип модели (`auto`, `ultralytics`, `onnx`, `rf_detr`, `d_fine`, `rtmdet`) | `"auto"` |
| `weights_path` | Путь к файлу модели | `"config/ultralytics/models/yolo11n.onnx"` |
| `confidence` | Минимальный порог уверенности детекции (0.0 – 1.0) | `0.6` |
| `iou` | Порог перекрытия Non-Maximum Suppression (IoU) | `0.7` |
| `device` | Устройство инференса (`0`, `"cpu"`, `"GPU"`, `"AUTO"`) | `0` |
| `vid_stride` | Шаг обработки кадров (1 — каждый кадр, 2 — каждый второй) | `1` |
| `video_show_scale` | Масштаб видео при передаче в веб-интерфейс (%) | `70` |
| `video_show_quality` | Качество JPEG-сжатия веб-видеопотока (1–100) | `50` |
| `video_fps` | Принудительный FPS видео (0 — авто) | `0` |
| `video_reconnect_attempts` | Макс. попыток переподключения к камере при сбое | `5` |
| `counting_areas` | Список полигональных зон подсчёта с цветами BGR и направлением движения | `[{"points": [[0,0],[100,0],[100,100],[0,100]], "color": [67,211,255], "direction": "top_to_bottom"}]` |
| `classes` | Фильтр и подписи классов для раздельного подсчёта | `{"0": "Коробка", "1": "Паллета"}` |
| `recording.enable` | Включение записи видео при детекции | `false` |
| `recording.path` | Папка сохранения видео | `"storage/saved_recordings"` |
| `recording.idle_timeout` | Время без детекций до остановки ролика (сек) | `30` |

---

## 🖥️ Веб-интерфейс и режимы работы

### 1. Дашборд (`/`)
Центральная панель мониторинга:
- Сводные карточки всех счётчиков с индикацией статуса (*Работает*, *Пауза*, *Остановлен*).
- Превью видеопотока в реальном времени.
- Кнопки быстрого управления: старт, пауза, сброс, настройки.
- Поиск и фильтрация счётчиков по статусу и имени.

### 2. Экран счётчика с видео (`/counter/<location>`)
Основное рабочее место оператора:
- Живое видео с наложением рамок детекции, траекторий трекера и полигонов зон.
- Сайдбар с ключевыми показателями: **Итог**, **Текущая партия**, **Брак**, **Коррекция**.
- Разворачиваемый блок **По классам** с детальной статистикой `партия / всего`.
- Форма ввода данных партии и пользовательских полей с сохранением в историю.

### 3. Текстовый режим (`/counter/<location>/text`)
Облегчённая версия интерфейса без передачи видео:
- Минимальное потребление ресурсов клиента и сети.
- Идеально подходит для мобильных терминалов сбора данных и планшетов на производстве.

### 4. Мульти-экран (`/counter_multi/text?locations=Cam1,Cam2`)
Сводный экран для одновременного контроля нескольких рабочих участков.

### 5. Интерактивный редактор зон (`/counter/<location>/counting_area`)
Визуальный инструмент разметки зон подсчёта прямо на стоп-кадре с камеры:
- Создание нескольких полигонов с независимыми цветами.
- **Векторы направления движения:** выбор направления для каждой зоны (8 направлений: вверх, вниз, влево, вправо и 4 диагонали, либо «любое») с фильтрацией по угловому сектору ($\pm 60^\circ$) и визуальной стрелкой вектора в центре зоны.
- Добавление, перетаскивание и удаление вершин.
- Быстрые шаблоны: «Весь кадр», «Прямоугольник по центру».
- Полноценная поддержка горячих клавиш в любой раскладке клавиатуры (RU/EN), история отмены и повтора (Undo/Redo: `Ctrl+Z`, `Ctrl+Y`).
- Автоматическая синхронизация зон с конфигурацией.

### 6. Отчёты и печать A4 (`/reports`)
- Просмотр журнала подсчётов с пагинацией и фильтрацией.
- Встроенный плеер сохранённых видеозаписей и просмотрщик фотофиксаций.
- Специализированный режим печати A4: автопереключение в светлую тему, скрытие элементов интерфейса, строгие таблицы и блок подписей ответственных лиц.

---

## 📚 Датасеты, разметка и обучение

Раздел `/datasets` предоставляет полный инструментарий подготовки собственных моделей детекции:

1. **Создание датасета:** указание имени, типа задачи (Detection / Segmentation) и списка классов.
2. **Импорт изображений:**
   - Загрузка локальных файлов или ZIP-архивов;
   - Ручной захват кадров с подключённых камер;
   - Автоматический интервальный сбор кадров из видеопотока;
   - Извлечение кадров из ранее сохранённых видеозаписей.
3. **Разметка:**
   - Разметка Bounding Box (`W`) и полигонов сегментации (`P`);
   - Поддержка горячих клавиш в любых раскладках (RU/EN), листание кадров (`A`/`D` или `←`/`→`), отмена и повтор (`Ctrl+Z`, `Ctrl+Y`);
   - Присвоение Track ID и атрибутов объектов;
   - Копирование разметки с предыдущего кадра для серийных снимков;
   - **Авторазметка (Autolabel):** автоматическая предварительная разметка с помощью базовых предобученных моделей (`Ctrl+A`);
   - **Active Learning:** приоритетный отбор наиболее информативных кадров для разметки.
4. **Обучение модели:**
   - Выбор training provider-а — обучение не привязано к какому-либо фреймворку;
   - Выбор базового чекпойнта из каталога, который выбранный provider реально умеет скачивать;
   - Настройка эпох, размера батча и разрешения входа;
   - Мониторинг прогресса обучения в реальном времени;
   - Автоматическое применение обученных весов к выбранному счётчику.

### Провайдеры обучения

Возможности обучения описаны декларативно: `BuiltinTrainingProvider`
(`system/training/registry.py`) объявляет задачи, форматы датасетов, форматы экспорта и
архитектуры, которые provider действительно поддерживает. Веб-интерфейс и API предлагают
только заявленное, поэтому задача «обучить и выгрузить в формат, которого provider не
делает» не возникает.

| Provider | Задачи | Формат датасета | Экспорт | Установка зависимостей | Лицензия |
|---|---|---|---|---|---|
| `ultralytics` | `detect`, `segment`, `classify`, `pose` | `yolo` (`.txt` + `data.yaml`) | `onnx`, `engine` | `python install.py --provider ultralytics` | AGPL-3.0 |
| `torchvision` | `detect` | `coco` (COCO JSON) | *не реализован* | `python install.py --provider pytorch` | BSD-3-Clause |

- Каждый provider хранит конфиги, базовые веса и прогоны в `config/<provider>/{cfg,models,runs}`;
  Ultralytics сохраняет исторический макет `config/ultralytics/` с откатом на старые
  `config/{cfg,models,runs}`.
- Прогоны находятся без импорта фреймворка: `list_runs()` и `find_run_weights()` перебирают
  `weights/best.pt`, `weights/model_final.pt`, `weights/best.pth` и `weights/model_final.pth`.
- `torchvision` дообучает Faster R-CNN (`fasterrcnn_resnet50_fpn_v2`) по COCO-аннотациям,
  но пока не выгружает развёртываемый файл модели. Вкладка обучения показывает предупреждение
  об этом и не предлагает ни одного формата экспорта.
- К шагу «применить веса к камере» допускаются только артефакты, которые читает реестр
  детекции (`.pt` Ultralytics, `.onnx`, `.engine`); чекпойнты provider-ов без экспорта
  остаются в списке прогонов `/datasets/api/training/runs` и в выпадающий список развёртывания
  не попадают.

Свой provider: наследуйте `BaseTrainingProvider` (`system/training/base.py`), реализуйте
единственный обязательный метод `train()` и — по необходимости — `export()`, `prepare()`,
`base_models()`, `supports_base_model()`, `download_base_model()`, после чего добавьте
запись `BuiltinTrainingProvider(...)` в `_BUILTIN_TRAINING_PROVIDERS`. Реестр импортирует
класс лениво и проверяет зависимости через `importlib.util.find_spec`, поэтому отсутствующий
фреймворк не ломает приложение: статус provider становится `unavailable`, а интерфейс
предлагает установить его командой из поля `install_provider`.

### Форматы выгрузки датасета

`export_for_training(name, dataset_format)` пишет один из вариантов `'yolo'`, `'coco'` или
`'both'`; параметр `dataset_format` (он же `format`) принимают веб-интерфейс и
`POST /datasets/api/<name>/export`. Нейтральный датасет лежит так:

```
storage/datasets/<name>/
├── images/{train,val}/…                     # исходные кадры
└── coco/annotations/instances_{split}.json  # COCO detection
```

Каждый JSON — стандартный COCO detection (`categories` с `id` от 1, `bbox [x, y, w, h]` в
абсолютных пикселях, `area`, а для `segment` ещё и `segmentation`) плюс собственные ключи:
верхнеуровневые `task`, `split`, `root` и относительный `path` у каждой записи кадра. По ним
provider находит изображения; если `root` отсутствует, отсчитываются три уровня вверх от
файла аннотаций.

### Автономный CLI `train.py`

```bash
python train.py providers
python train.py list --provider ultralytics
python train.py list --provider torchvision
python train.py train --config road-map --provider ultralytics --epochs 100 --export onnx
python train.py train --config road-map --provider torchvision --epochs 20 --imgsz 800 --batch 2
python train.py export --config road-map --provider ultralytics --export engine
```

`--provider auto` выбирает provider по задаче и формату датасета, `--dataset-format` задаёт
его явно; `train.py` отказывается запускать задачу, которую выбранный provider не объявляет.

---

## 🔌 Справочник REST API

### Управление счётчиками (`routes/counters.py`)

| Метод | URL | Описание |
|---|---|---|
| `GET` | `/counter/<location>/bootstrap` | Инициализация и запуск фонового потока счётчика |
| `GET`, `POST` | `/start_count/<location>` | Запуск / возобновление подсчёта |
| `GET`, `POST` | `/pause_count/<location>` | Приостановка подсчёта (пауза) |
| `GET`, `POST` | `/stop_count/<location>` | Полная остановка счётчика и освобождение видеоисточника |
| `POST` | `/save_count/<location>` | Сохранение текущей партии и полей формы в БД |
| `GET`, `POST` | `/reset_count/<location>` | Полный сброс общего счётчика |
| `POST` | `/reset_count_current/<location>` | Сброс счётчика текущей сессии/партии |
| `POST` | `/update_pending_counts/<location>` | Коррекция временных значений счёта/брака |
| `GET`, `POST` | `/save_capture/<location>` | Сохранение единичного снимка с камеры в хранилище |
| `GET`, `POST` | `/counter/<location>/capture/interval` | Настройка интервального сохранения кадров |
| `GET` | `/counter_get_frames/<location>` | Потоковая передача видео в формате MJPEG |
| `GET` | `/counter/<location>/preview` | Получение последнего JPEG-превью кадра |
| `GET` | `/counter/<location>/settings/form` | HTML-форма настроек камеры для модального окна |
| `POST` | `/counter/<location>/settings` | Обновление настроек детекции для камеры |
| `GET` | `/counter/<location>/counting_area/data` | JSON с текущими зонами подсчёта |
| `GET` | `/counter/<location>/counting_area/snapshot` | Получение стоп-кадра для редактора зон |
| `POST` | `/counter/<location>/counting_area` | Сохранение новых координат зон подсчёта |

### Настройки и система (пакет `routes/settings/` — требует авторизации)

| Метод | URL | Описание |
|---|---|---|
| `POST` | `/settings_save` | Сохранение глобальной конфигурации системы |
| `POST` | `/settings/api/detections/add` | Добавление новой камеры в конфигурацию |
| `POST` | `/settings/api/detections/<location>/delete` | Удаление камеры из конфигурации |
| `POST` | `/settings/api/custom_fields/add` | Создание динамического пользовательского поля |
| `POST` | `/settings/api/custom_fields/delete` | Удаление пользовательского поля |
| `POST` | `/settings/api/model_classes` | Извлечение списка классов напрямую из файла модели |
| `GET` | `/settings/api/runtimes/status` | Проверка доступности аппаратных рантаймов (CUDA, OpenVINO) |
| `POST` | `/settings/api/runtimes/install` | Запуск установки недостающего AI-рантайма |
| `GET` | `/settings/api/runtimes/install/status` | Опрос статуса процесса установки рантайма |
| `GET` | `/settings/api/models/list` | Список доступных файлов моделей в системе |
| `POST` | `/settings/api/models/export` | Запуск задачи экспорта модели (ONNX, TensorRT Engine) |
| `GET` | `/settings/api/models/export/status` | Прогресс задачи экспорта модели |
| `GET` | `/settings/api/logs` | Чтение журнала логов с фильтрацией и пагинацией |
| `GET` | `/settings/api/logs/download` | Скачивание полного файла логов приложения |
| `POST` | `/settings/api/logs/clear` | Очистка файла логов |
| `POST` | `/settings/api/restart` | Перезапуск веб-сервера |
| `POST` | `/settings/api/shutdown` | Завершение работы веб-сервера |

### Датасеты (`routes/datasets.py` — требует авторизации)

| Метод | URL | Описание |
|---|---|---|
| `GET` | `/datasets/api/list` | Список всех датасетов и их статус |
| `POST` | `/datasets/api/create` | Создание нового датасета |
| `DELETE` | `/datasets/api/<name>` | Удаление датасета |
| `GET` | `/datasets/api/<name>/summary` | Статистика кадров, классов и разметки |
| `POST` | `/datasets/api/<name>/capture-camera` | Захват стоп-кадра с камеры в датасет |
| `POST` | `/datasets/api/<name>/import/upload` | Загрузка изображений или архива в датасет |
| `POST` | `/datasets/api/<name>/split` | Автоматическое разделение на выборки train/val |
| `GET`, `POST`| `/datasets/api/<name>/annotations/<image>` | Чтение и запись разметки конкретного кадра |
| `POST` | `/datasets/api/<name>/export` | Выгрузка датасета в `yolo`, `coco` или `both` (параметр `dataset_format`) |
| `GET` | `/datasets/api/<name>/export-zip` | ZIP-архив датасета сразу в обоих форматах |
| `POST` | `/datasets/api/<name>/autolabel` | Пакетная авторазметка изображений моделью |
| `GET` | `/datasets/api/models/base` | Каталог базовых чекпойнтов provider-а (`?provider=`) |
| `POST` | `/datasets/api/<name>/train` | Запуск обучения: параметры `provider` и `base_model` |
| `GET` | `/datasets/api/training/status` | Мониторинг прогресса обучения |
| `POST` | `/datasets/api/training/cancel` | Прерывание задачи обучения |
| `GET` | `/datasets/api/training/runs` | Список завершённых прогонов (`?provider=`, `?task=`) |
| `POST` | `/datasets/api/training/apply-weights` | Применение весов обученной модели к камере |

### Программный REST API v1 (пакет `routes/api/v1/` — префикс `/api/v1`)

| Метод | URL | Описание |
|---|---|---|
| `GET` | `/api/v1/counters` | Список всех настроенных счётчиков и их текущий статус |
| `GET` | `/api/v1/counters/<location>` | Текущие показатели и статус конкретного счётчика |
| `POST` | `/api/v1/counters/<location>/start` | Запуск подсчёта на счётчике |
| `POST` | `/api/v1/counters/<location>/pause` | Приостановка подсчёта (пауза) |
| `POST` | `/api/v1/counters/<location>/stop` | Остановка счётчика |
| `POST` | `/api/v1/counters/<location>/reset` | Сброс общего счётчика |
| `POST` | `/api/v1/counters/<location>/save` | Сохранение текущей партии и полей формы |
| `GET` | `/api/v1/counters/<location>/snapshot` | Получение текущего снимка кадра |
| `GET` | `/api/v1/reports` | Список сохранённых отчётов |
| `GET` | `/api/v1/reports/<id>` | Детальная информация по конкретному отчёту |
| `DELETE` | `/api/v1/reports/<id>` | Удаление отчёта из базы данных |
| `GET` | `/api/v1/system/health` | Проверка жизнеспособности сервиса (healthcheck) |
| `GET` | `/api/v1/system/info` | Системная информация (версия, ОС, GPU, доступные рантаймы) |

---

## 🔐 Аутентификация и сессии

- Авторизация работает на базе зашифрованных cookie Flask-сессий.
- Пользователи и scrypt-хэши паролей задаются в `config/config.json` в блоке `users`.
- Если блок `users` пуст или не содержит записей, система работает в открытом режиме без запроса пароля.
- Защищённые разделы (требуют `@login_required`):
  - `/settings` (настройки конфигурации и рантаймов);
  - `/system_info` (системная информация и логи);
  - `/datasets` (все операции с данными и обучением).
- Публичные разделы: дашборд, экраны счётчиков, просмотр отчётов и справка.

---

## ⚡ Real-time события (Socket.IO)

Клиентские веб-страницы получают оперативные обновления через WebSocket/Socket.IO в реальном времени:

| Имя события | Данные (Payload) | Описание |
|---|---|---|
| `{location}_count` | `{total, current, defect, correct, pending_*, by_class: [...]}` | Передача новых значений счётчиков и раскладки по классам |
| `{location}_notification` | `{type: "success"|"warning"|"error", message: "..."}` | Оповещения оператора о событиях (сохранение партии, ошибка) |
| `counter_status_event` | `{data: {status: "started"|"paused"|"stopped"|"error", location: "..."}}` | Смена жизненного цикла потока камеры |

---

## ❓ Часто задаваемые вопросы (FAQ)

### 1. Какие требования к оборудованию сервера?
- **CPU:** 4-ядерный процессор (Intel Core i5 / AMD Ryzen 5 или выше).
- **RAM:** от 8 ГБ (рекомендуется 16 ГБ при работе с несколькими потоками).
- **GPU:**
  - *NVIDIA GeForce GTX 1050 Ti (4 ГБ):* до 5–6 одновременных потоков детекции с YOLOv8n/YOLO11n.
  - *NVIDIA RTX 3060 / 4060 (8–12 ГБ):* до 15–20 потоков реального времени или комфортное обучение моделей.
  - *Intel Arc / встроенная графика iGPU:* аппаратное ускорение через OpenVINO без дискретной видеокарты.

### 2. Как запустить браузер в режиме киоска для оператора?
Чтобы оператор не мог свернуть браузер или закрыть окно, настройте автозапуск Chromium/Chrome:
```bash
google-chrome --kiosk --start-fullscreen http://localhost:8080/counter/Line1
```

### 3. Камера часто обрывает RTSP-соединение, что делать?
Увеличьте параметр `video_reconnect_attempts` (например, до `10` или `20`) в конфигурации камеры. Приложение будет автоматически восстанавливать соединение при кратковременных сетевых сбоях.

### 4. Где найти сохранённые видеозаписи и кадры?
Все медиафайлы сохраняются в директории `storage/` (`storage/saved_recordings` и `storage/saved_images`). Также их можно просматривать и скачивать прямо из веб-интерфейса во вкладке **Отчёты ➔ Сохранённые медиа**.

---

## 🤝 Вклад в проект и лицензия

Приветствуются любые предложения, сообщения об ошибках и Pull Request'ы!
1. Форкните репозиторий [BespredeL/CVCounter](https://github.com/BespredeL/CVCounter).
2. Создайте ветку для новой функциональности (`git checkout -b feature/my-feature`).
3. Зафиксируйте изменения (`git commit -m 'Add new feature'`).
4. Отправьте ветку на GitHub (`git push origin feature/my-feature`) и откройте PR.

Проект распространяется под свободной лицензией **[GNU AGPLv3](https://github.com/BespredeL/CVCounter/blob/master/LICENSE)**.

У каждого training provider-а свои условия: Ultralytics лицензирован под **AGPL-3.0**,
PyTorch и torchvision — под **BSD-3-Clause**. Если установить только provider `pytorch`,
Ultralytics не участвует в обучении вовсе.
