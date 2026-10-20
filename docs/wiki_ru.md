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
- 🔄 **Высокоточный трекинг (ByteTrack):** устойчивое отслеживание объектов между кадрами с предотвращением повторного подсчёта.
- 🏷️ **Разбивка по классам:** подсчёт суммарного количества и количества в текущей партии по каждому обнаруженному классу.
- 🎥 **Гибкие источники видео:** RTSP/RTMP-потоки IP-камер, локальные веб-камеры (USB/V4L2) и видеофайлы.
- 🎬 **Умная видеозапись:** автоматический старт записи видео при появлении детекций и остановка по настраиваемому таймауту неактивности (`idle_timeout`).
- 🧠 **Поддержка любых моделей:** автоматический выбор или явное указание рантайма (ONNX Runtime, Intel OpenVINO, OpenCV DNN, Ultralytics YOLO).
- 📚 **Полный цикл работы с датасетами:** сбор кадров из потока, разметка боксов/полигонов, активное обучение (Active Learning), авторазметка, обучение YOLO и применение обученных весов в 1 клик.
- 📊 **Отчёты и аналитика:** журнал сессий с разбивкой по партиям, брак/коррекция, просмотр сохранённых кадров и видео, печать и экспорт в A4 PDF.
- 🚀 **1-Click установщик:** скрипт `install.bat` / `install.sh` автоматически распознаёт модель GPU (NVIDIA CUDA, AMD DirectML, Intel Arc / OpenVINO) и собирает готовое окружение.
- 🛠️ **Управление рантаймами (AI Runtimes Center):** проверка статуса CUDA, TensorRT, OpenVINO и доустановка библиотек через веб-интерфейс.
- 🔐 **Безопасность:** авторизация администратора, защита настроек и датасетов, шифрование паролей scrypt.

---

## 🏛️ Архитектура приложения

Приложение построено по модульной схеме с использованием паттерна Application Factory во Flask:

```
CVCounter/
├── app.py                      # Точка входа, регистрация blueprints и socketio
├── train.py                    # Автономный CLI-скрипт обучения и экспорта YOLO
├── install.py                  # Универсальный кроссплатформенный установщик
├── config/                     # Файлы конфигурации и веса моделей
│   ├── config.json             # Рабочий файл настроек
│   ├── config.example.json     # Эталонный файл настроек
│   ├── database.sqlite         # База данных SQLite (сессии, отчёты)
│   └── ultralytics/            # Модели и конфиги Ultralytics YOLO
├── routes/                     # Модули представлений (Blueprints)
│   ├── main.py                 # Дашборд, авторизация, статические страницы
│   ├── counters.py             # Счётчики, видеопотоки, редактор зон, API подсчёта
│   ├── reports.py              # Просмотр отчётов, медиафайлы, экспорт
│   ├── datasets.py             # Датасеты, разметка, обучение моделей
│   └── settings.py             # Настройки, системная информация, рантаймы, логи
├── system/                     # Внутреннее ядро системы
│   ├── core/                   # Логика трекинга и подсчёта (ObjectCounter)
│   ├── object_detection/       # Абстракции и реализации бэкендов детекции
│   ├── managers/               # Менеджеры потоков, БД, уведомлений, обучения
│   ├── datasets/               # Хранилище аннотаций и сервис датасетов
│   ├── training/               # Обучение и экспорт моделей
│   └── utils/                  # I18n, телеметрия, валидаторы, логгер
├── static/                     # CSS, JS, шрифты и иконки
├── templates/                  # Шаблоны Jinja2
└── storage/                    # Логи, сохранённые кадры, записи, датасеты
```

### Основные Blueprints:

| Blueprint | Модуль | Префикс URL | Назначение |
|---|---|---|---|
| `main` | `routes/main.py` | `/` | Дашборд, авторизация (`/login`, `/logout`), справка (`/page/help`) |
| `counters` | `routes/counters.py` | `/` | Экраны счётчиков, видео MJPEG, редактор зон, сохранение партий |
| `reports` | `routes/reports.py` | `/reports` | История сессий, сохранённые кадры/видео, печатные формы A4 |
| `datasets` | `routes/datasets.py` | `/datasets` | Подготовка данных, разметка, обучение моделей (*auth*) |
| `settings` | `routes/settings.py` | `/settings`, `/system_info` | Конфигуратор, системный статус, консоль логов, рантаймы (*auth*) |

---

## 📦 Установка и запуск

### Способ 1: Автоматическая установка в 1 клик (Рекомендуется)

Установщик `install.py` определяет установленную видеокарту, выбирает правильную версию PyTorch и ONNX Runtime, создаёт виртуальное окружение `venv` и генерирует конфигурацию:

- **Windows:** дважды кликните на `install.bat`. Для запуска используйте `start.bat`.
- **Linux / macOS:**
  ```bash
  chmod +x install.sh start.sh
  ./install.sh
  ./start.sh
  ```

#### Поддерживаемые профили оборудования:
- **`nvidia_cuda`:** Автоматический подбор версии CUDA (12.4 / 12.1 / 11.8), установка `torch` с CUDA и `onnxruntime-gpu`.
- **`amd_directml`:** Ускорение через DirectX DirectML (`torch-directml`, `onnxruntime-directml`) на видеокартах AMD Radeon в Windows (в Linux — ROCm).
- **`intel_openvino`:** Оптимизация под процессоры Intel Core/Xeon, встроенную графику iGPU, видеокарты Intel Arc и NPU.
- **`cpu`:** Универсальный режим без графического ускорителя.

Флаги установщика:
```bash
python install.py --profile nvidia_cuda  # Принудительный выбор профиля
python install.py --reinstall            # Переустановка всех пакетов
python install.py --no-color             # Отключение ANSI-цветов
```

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
   
   # Опционально: для обучения YOLO и моделей .pt
   pip install -r requirements-ultralytics.txt

   # Опционально: для ускорения Intel OpenVINO
   pip install -r requirements-openvino.txt
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

Реестр сервисов детекции (`system/object_detection/registry.py`) позволяет подключать любые нейросетевые бэкенды через единый интерфейс `BaseObjectDetectionService`.

### Поддерживаемые значения `model_type`:

| `model_type` | Бэкенд | Лицензия | Поддерживаемые форматы | Рекомендуемое применение |
|---|---|---|---|---|
| **`auto`** | Автоопределение | — | `.onnx`, `.pt`, `.engine`, `.xml` | **По умолчанию.** Выбирает движок на основе расширения файла модели |
| **`onnx`**, `onnxruntime` | [ONNX Runtime](https://onnxruntime.ai/) | MIT | `.onnx` (YOLOv5–v11, RT-DETR) | Кроссплатформенный инференс с максимальной скоростью (CUDA, DirectML, CPU) |
| **`openvino`**, `openvino_dnn` | [Intel OpenVINO](https://www.intel.com/openvino) | Apache-2.0 | `.xml`/`.bin`, `.onnx` | Наилучшая производительность на процессорах Intel, видеокартах Arc и iGPU |
| **`yolo`**, `ultralytics` | [Ultralytics YOLO](https://github.com/ultralytics/ultralytics) | AGPL-3.0 | `.pt`, `.engine` (TensorRT) | Нативный PyTorch, TensorRT Engine, обучение моделей |
| **`opencv`**, `opencv_dnn` | [OpenCV DNN](https://docs.opencv.org) | Apache-2.0 | `.onnx`, Darknet (`.weights` + `.cfg`) | Легковесный режим без зависимостей PyTorch |

### Примеры конфигурации детектора

**Автоматический выбор (рекомендуется):**
```json
{
  "model_type": "auto",
  "weights_path": "config/ultralytics/models/yolo11n.onnx"
}
```

**ONNX Runtime с аппаратными провайдерами:**
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

### Добавление собственного детектора

1. Создайте класс-наследник `BaseObjectDetectionService`:
   ```python
   from system.object_detection.base_object_detection import BaseObjectDetectionService, DetectionResult
   from system.object_detection.registry import register

   @register('custom_detector')
   class CustomDetector(BaseObjectDetectionService):
       def load_model(self, weights: str, **kwargs) -> None:
           # Инициализация модели
           pass

       def detect(self, image, **kwargs) -> DetectionResult:
           # Инференс: возврат boxes_xyxy, confidences, classes
           pass
   ```
2. Зарегистрируйте модуль в `system/object_detection/__init__.py`.
3. Укажите `"model_type": "custom_detector"` в конфигурации камеры.

---

## ⚙️ Полный справочник конфигурации (`config.json`)

Файл конфигурации разделен на логические секции:

### 1. `general` — Общие параметры системы

| Параметр | Описание | По умолчанию |
|---|---|---|
| `debug` | Режим отладки Flask | `true` |
| `system_check` | Вывод параметров GPU/CUDA/PyTorch в лог при запуске | `true` |
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

### 6. `telemetry` — Опциональная диагностика

| Параметр | Описание | По умолчанию |
|---|---|---|
| `enabled` | Автоматическая фоновая отправка данных об ошибках | `false` |
| `endpoint` | HTTPS-эндпоинт приёмника телеметрии | `"https://bespredel.name/api/cvcounter/telemetry"` |
| `send_errors` | Отправка неперехваченных исключений | `true` |
| `send_usage` | Отправка анонимных событий использования | `true` |
| `flush_interval_sec`| Интервал фонового сброса очереди (секунды) | `300` |
| `timeout_sec` | HTTP-таймаут запроса телеметрии | `5` |
| `hmac_secret` | Секретный ключ подписи заголовка `X-CVCounter-Signature` | `""` |

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
| `model_type` | Тип модели (`auto`, `yolo`, `onnx`, `openvino`, `opencv`) | `"auto"` |
| `weights_path` | Путь к файлу модели | `"config/ultralytics/models/yolo11n.onnx"` |
| `confidence` | Минимальный порог уверенности детекции (0.0 – 1.0) | `0.6` |
| `iou` | Порог перекрытия Non-Maximum Suppression (IoU) | `0.7` |
| `device` | Устройство инференса (`0`, `"cpu"`, `"GPU"`, `"AUTO"`) | `0` |
| `vid_stride` | Шаг обработки кадров (1 — каждый кадр, 2 — каждый второй) | `1` |
| `video_show_scale` | Масштаб видео при передаче в веб-интерфейс (%) | `70` |
| `video_show_quality` | Качество JPEG-сжатия веб-видеопотока (1–100) | `50` |
| `video_fps` | Принудительный FPS видео (0 — авто) | `0` |
| `video_reconnect_attempts` | Макс. попыток переподключения к камере при сбое | `5` |
| `counting_areas` | Список полигональных зон подсчёта с цветами BGR | `[{"points": [[0,0],[100,0],[100,100],[0,100]], "color": [67,211,255]}]` |
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
- Добавление, перетаскивание и удаление вершин.
- Быстрые шаблоны: «Весь кадр», «Прямоугольник по центру».
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
   - Разметка Bounding Box и полигонов сегментации;
   - Присвоение Track ID и атрибутов объектов;
   - Копирование разметки с предыдущего кадра для серийных снимков;
   - **Авторазметка (Autolabel):** автоматическая предварительная разметка с помощью базовых предобученных моделей;
   - **Active Learning:** приоритетный отбор наиболее информативных кадров для разметки.
4. **Обучение модели:**
   - Выбор базовой архитектуры (YOLO11, YOLOv8 и др.);
   - Настройка эпох, размера батча и разрешения входа;
   - Мониторинг прогресса обучения в реальном времени;
   - Автоматическое применение обученных весов `best.pt` к выбранному счётчику.

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

### Настройки и система (`routes/settings.py` — требует авторизации)

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
| `POST` | `/datasets/api/<name>/autolabel` | Пакетная авторазметка изображений моделью |
| `POST` | `/datasets/api/<name>/train` | Запуск процесса обучения нейросети |
| `GET` | `/datasets/api/training/status` | Мониторинг прогресса обучения |
| `POST` | `/datasets/api/training/cancel` | Прерывание задачи обучения |
| `POST` | `/datasets/api/training/apply-weights` | Применение обученной модели `best.pt` к камере |

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

Мы приветствуем предложения, сообщения об ошибках и Pull Request'ы!
1. Форкните репозиторий [BespredeL/CVCounter](https://github.com/BespredeL/CVCounter).
2. Создайте ветку для новой функциональности (`git checkout -b feature/my-feature`).
3. Зафиксируйте изменения (`git commit -m 'Add new feature'`).
4. Отправьте ветку на GitHub (`git push origin feature/my-feature`) и откройте PR.

Проект распространяется под свободной лицензией **[GNU AGPLv3](https://github.com/BespredeL/CVCounter/blob/master/LICENSE)**.
