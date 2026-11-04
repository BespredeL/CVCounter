# CVCounter - Система детекции и подсчёта объектов

[![Website](https://img.shields.io/badge/website-cvcounter.createdby.ru-4dabf7.svg)](https://cvcounter.createdby.ru)
[![Author](https://img.shields.io/badge/author-bespredel.name-8a2be2.svg)](https://bespredel.name)
[![Readme EN](https://img.shields.io/badge/README-EN-blue.svg)](https://github.com/BespredeL/CVCounter/blob/master/README_EN.md)
[![Readme RU](https://img.shields.io/badge/README-RU-blue.svg)](https://github.com/BespredeL/CVCounter/blob/master/README.md)
[![GitHub license](https://img.shields.io/badge/license-AGPL--3.0-458a7b.svg)](https://github.com/BespredeL/CVCounter/blob/master/LICENSE)

🧠 Готовая система компьютерного зрения для детекции, трекинга и подсчёта объектов в реальном времени.

CVCounter — это гибкая и производительная веб-система компьютерного зрения для анализа видеопотоков. Решение разворачивается в виде локального веб-сервиса на Flask, что избавляет от необходимости устанавливать клиентское ПО на рабочие места операторов.

---

## ✨ Возможности

- 🎯 **Детекция и трекинг:** отслеживание объектов и подсчёт в реальном времени в одной или нескольких настраиваемых зонах с фильтрацией направления движения (8 векторов).
- 🎥 **Источники видео:** поддержка RTSP-потоков, USB/веб-камер и локальных видеофайлов, автоматическая запись видео по событиям детекции.
- 🏷️ **Классификация:** подсчёт с разбивкой по классам объектов и гибкая фильтрация классов.
- 📚 **Работа с датасетами:** импорт кадров (из потока, архивов ZIP, записей), разметка боксов и полигонов, выгрузка в YOLO и COCO, обучение через подключаемые training provider-ы (Ultralytics YOLO, torchvision) и применение обученных весов.
- 🧠 **Мультиархитектурная платформа Object Detection:** независимый Detection Engine с поддержкой архитектур **Ultralytics YOLO**, **Roboflow RF-DETR**, **Peterande D-FINE** и **OpenMMLab RTMDet**, а также универсального ONNX Runtime. Подробнее: [`docs/multi_architecture_guide.md`](docs/multi_architecture_guide.md).
- ⚡ **Аппаратные бэкенды инференса:** полноценная поддержка PyTorch CUDA, PyTorch CPU, ONNX Runtime (CPU/CUDA) и NVIDIA TensorRT FP16.
- 🏋️ **Training Engine & Fine-tuning:** независимая подсистема обучения и дообучения моделей на пользовательских датасетах, сохранение и загрузка checkpoints (`best.pth`, `last.pth`), валидация и экспорт в ONNX.
- 📁 **Dataset Engine:** валидация датасетов (YOLO TXT и COCO JSON), контроль границ боксов, предотвращение утечек данных между последовательностями видео и двухсторонняя конвертация.
- 📊 **Отчёты и аналитика:** история партий и смен, статистика по классам, просмотр сохранённых медиа, экспорт и печать отчётов в формате A4.
- 🚀 **Автоустановка в один клик:** скрипт автоматически определяет GPU (NVIDIA CUDA, AMD DirectML, Intel OpenVINO) и настраивает изолированное окружение.
- 🛠️ **Управление рантаймами:** диагностика доступности аппаратного ускорения и доустановка библиотек инференса прямо из интерфейса.
- 🔌 **REST API v1:** полноценный программный интерфейс для интеграции с CRM, 1С, Telegram-ботами и внешними сервисами (аутентификация по API-ключам, роли доступа, управление камерами, отчёты и моментальные снимки). Подробнее: [`docs/api.md`](docs/api.md).
- 🔐 **Веб-интерфейс:** авторизация пользователей, удобный редактор зон подсчёта, динамические поля формы партии, журнал событий и статус системы.

> [!TIP]
> **Анонимная телеметрия:**  
> В проект включена отправка анонимных данных об ошибках и стабильности для помощи в развитии проекта (включена по умолчанию, можно отключить в настройках: `telemetry.enabled: false`).  
> Кадры с камер, URL видеопотоков и пароли **никогда не отправляются**.  
> Подробнее: [`docs/telemetry_api.md`](docs/telemetry_api.md).

---

## 🚀 Применение

- 🏭 **Производство и склады:** подсчёт готовой продукции на конвейере, контроль тары и паллет.
- 🏬 **Ритейл и ТЦ:** подсчёт посетителей, контроль очередей и анализ трафика.
- 🚗 **Транспорт и парковки:** учёт автомобилей, интенсивность движения.
- 🛡️ **Безопасность:** контроль пересечения периметра и запретных зон.

---

## 🧠 Как это работает

```mermaid
flowchart LR
    A[Видеопоток<br>RTSP / Камера / Файл] --> B[Детекция объектов<br>YOLO / ONNX / DETR]
    B --> C[Трекинг<br>Присвоение ID]
    C --> D{Пересечение<br>зон подсчёта}
    D -- Да --> E[Фиксация подсчёта<br>Классы / Партии]
    E --> F[Веб-интерфейс,<br>Отчёты и Запись медиа]
```

1. **Захват видеопотока:** непрерывное чтение кадров с камеры или файла.
2. **Инференс:** поиск объектов с помощью выбранной модели.
3. **Трекинг:** присвоение устойчивых трек-номеров объектам между кадрами.
4. **Контроль зон:** фиксация объекта при входе в любую из заданных полигональных зон.
5. **Учёт и сохранение:** обновление счётчиков, разбивка по классам и сохранение в базу данных и отчёты.

---

## 📦 Установка

### Вариант 1: Автоматическая установка в 1 клик (Рекомендуется)

Установщик автоматически определит установленное оборудование (NVIDIA CUDA, AMD DirectML, Intel OpenVINO или CPU), создаст виртуальное окружение, установит зависимости и подготовит конфигурацию:

- **Windows:**  
  Запустите **`install.bat`**.  
  Для запуска приложения используйте **`start.bat`**.

- **Linux / macOS:**
  ```bash
  chmod +x install.sh start.sh
  ./install.sh
  ./start.sh
  ```

> **Опции установщика (`install.py`):**
> - `--profile [nvidia_cuda|amd_directml|intel_openvino|cpu]` — принудительный выбор аппаратного профиля
> - `--with-inference` — дополнительно установить ONNX Runtime для выбранного профиля (с поддержкой CUDA/DirectML/OpenVINO)
> - `--with-pytorch` — дополнительно установить PyTorch для ML-провайдеров, которым он нужен
> - `--with-ultralytics` — дополнительно установить PyTorch и Ultralytics для моделей `.pt` и обучения
> - `--provider <name>` — выбрать встроенный provider; флаг можно повторять для нескольких: `onnxruntime`, `openvino`, `pytorch`, `ultralytics`
> - `--reinstall` — принудительная переустановка зависимостей
> - `--no-color` — отключение цветного вывода в терминале

По умолчанию установщик ставит только Core, без PyTorch, Ultralytics и ONNX Runtime.
Для высокопроизводительного инференса ONNX Runtime используйте `--with-inference`.
Для `.pt`-моделей, авторазметки и обучения YOLO используйте `--with-ultralytics`.
Отдельные runtime providers можно выбрать, например, командами
`python install.py --provider onnxruntime` или
`python install.py --provider onnxruntime --provider ultralytics`.
OpenCV входит в Core и используется для захвата видео и операций с изображениями.

---

### Вариант 2: Ручная установка

1. **Клонируйте репозиторий:**
   ```bash
   git clone https://github.com/BespredeL/CVCounter.git
   cd CVCounter
   ```

2. **Создайте и активируйте виртуальное окружение:**
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

3. **Установите зависимости:**
   ```bash
   pip install -r requirements.txt
   ```
   *(Опционально)* Для инференса через ONNX Runtime CPU:
   ```bash
   pip install -r requirements-onnxruntime.txt
   ```
   *(Опционально)* Для работы с весами `.pt` и обучения YOLO:
   ```bash
   pip install -r requirements-ultralytics.txt
   ```
   *(Опционально)* Для аппаратного ускорения Intel OpenVINO:
   ```bash
   pip install -r requirements-openvino.txt
   ```
   *(Опционально)* Для ONNX export/optimization:
   ```bash
   pip install -r requirements-onnx-export.txt
   ```

4. **Подготовьте файл конфигурации:**
   ```bash
   cp config/config.example.json config/config.json
   ```

5. **Запустите приложение:**
   ```bash
   python app.py
   ```
   Сервер будет доступен по адресу: `http://localhost:8080` (по умолчанию логин/пароль: `admin` / `admin`).

---

### Вариант 3: Установка через Docker Compose

```bash
git clone https://github.com/BespredeL/CVCounter.git
cd CVCounter
docker-compose up --build
```

Эта команда сохраняет прежний NVIDIA/CUDA deployment. Для Core-образа без
PyTorch/Ultralytics используйте отдельную конфигурацию:

```bash
docker compose -f docker-compose.core.yml up --build
```

---

## 🖥️ Использование и режимы работы

Интерфейс спроектирован для удобной работы операторов на мониторах и планшетах:

1. **Основной вид (`/counters/<label>`)** — отображение текущего счёта, партии, формы ввода брака/коррекции и живого видеопотока с наложением боксов и зон.
2. **Текстовый вид (`/counters/<label>/text`)** — облегчённый экран только со счётчиками для слабых клиентов и экономии трафика.
3. **Мульти-экран (`/counters/multi/text`)** — сводный мониторинг всех камер на одном экране.
4. **Датасеты (`/datasets`)** — сбор кадров из потока, разметка боксов/полигонов и запуск обучения моделей прямо из браузера.
5. **Отчёты (`/reports`)** — фильтрация истории подсчётов, просмотр фотофиксаций и сохранённых видеозаписей, экспорт и печать.

> [!TIP]
> **Режим киоска для операторов:**  
> Для блокировки выхода из браузера на рабочем месте оператора запускайте Chrome в полноэкранном режиме:  
> `google-chrome --kiosk --start-fullscreen http://localhost:8080/counters/ExampleCam`

> **Ориентир производительности:**  
> На тестовом сервере (AMD Ryzen 5 3600, NVIDIA GTX 1050 Ti 4GB) система стабильно обрабатывает до 5–6 одновременных видеопотоков с детекцией в реальном времени.

---

## 📚 Датасеты и обучение

Встроенный модуль работы с датасетами позволяет обучать кастомные модели под ваши объекты:

1. Создайте датасет и загрузите кадры (через веб-интерфейс, ZIP-архив или автосбор из видеопотока).
2. Выполните разметку объектов (bounding box или полигоны).
3. Выберите training provider (Ultralytics YOLO или torchvision) и запустите обучение из интерфейса.
4. Примените полученные веса к нужному счётчику в один клик.

Датасет выгружается в формате YOLO (`.txt` + `data.yaml`) и в нейтральном COCO JSON
(`storage/datasets/<name>/coco/annotations/`), поэтому модель можно дообучать в любом
фреймворке, а не только в Ultralytics.

Также доступно управление обучением через консольный интерфейс:
```bash
python train.py providers
python train.py train --config my-dataset --provider ultralytics --epochs 100 --export onnx
python train.py train --config my-dataset --provider torchvision --epochs 20
python train.py export --config my-dataset --export onnx
```

---

## 🧠 Поддерживаемые архитектуры и бэкенды детекции

В конфигурации счётчика задаётся параметр `model_type` (или `"auto"` для автоопределения по имени файла и расширению):

| `model_type` | Архитектура / Движок | Лицензия | Форматы моделей | Особенности |
|---|---|---|---|---|
| **`auto`** | Автовыбор | — | `.onnx`, `.pt`, `.engine`, `.pth` | Рекомендуется: автоматически определяет архитектуру по имени файла и формату |
| **`yolo`**, `ultralytics` | [Ultralytics YOLO](https://github.com/ultralytics/ultralytics) | AGPL-3.0 | `.pt`, `.engine` (TensorRT) | YOLOv8–YOLO26, нативный PyTorch, TensorRT engine, трекинг |
| **`onnx`**, `onnxruntime` | [ONNX Runtime](https://onnxruntime.ai/) | MIT | `.onnx` (YOLO, DETR, RTMDet) | Высокая скорость, динамические провайдеры CUDA, DirectML, OpenVINO, CPU |
| **`rf_detr`** | [Roboflow RF-DETR](https://github.com/roboflow/rf-detr) | Apache-2.0 | `.pth`, `.pt`, `.onnx` | Трансформерные детекторы RF-DETR (Nano, Small, Medium, Large) |
| **`d_fine`** | [Peterande D-FINE](https://github.com/Peterande/D-FINE) | Apache-2.0 | `.pth`, `.pt`, `.onnx` | Real-time DETR с распределением регрессии границ (N/S/M/L/X) |
| **`rtmdet`** | [OpenMMLab RTMDet](https://github.com/open-mmlab/mmdetection) | Apache-2.0 | `.pth`, `.onnx` | Сверхбыстрые детекторы OpenMMLab RTMDet (Tiny, S, M, L, X) |

### Основные параметры детекции

| Параметр | Применимо к | Описание |
|---|---|---|
| `weights_path` | Все | Путь к файлу модели (`.onnx`, `.pt`, `.engine`, `.pth`) |
| `confidence`, `iou` | Все | Пороги уверенности детекции и NMS IoU |
| `device` | Все | Устройство инференса (`0`, `"cpu"`, `"cuda"`, `"cuda:0"`) |
| `input_size` | ONNX, DETR, YOLO | Размер входа модели (`640` или `[640, 640]`) |
| `vid_stride` | Все | Шаг кадров (пропуск кадров для снижения нагрузки) |
| `classes` | Все | Фильтр классов и пользовательские названия, напр.: `{"0": "Коробка"}` |
| `counting_areas` | Все | Список полигонов зон подсчёта, их цвета в формате BGR и векторы направления движения |

---

## ⚙️ Конфигурация

Все параметры системы хранятся в `config/config.json`. При первом запуске файл создаётся на основе `config/config.example.json`.

Базовая структура конфигурации:

```json5
{
    "general": {
        "debug": false,
        "default_language": "ru",
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
            "label": "Линия упаковки №1",
            "video_path": "rtsp://admin:pass@192.168.1.50:554/stream1",
            "model_type": "auto",
            "weights_path": "config/ultralytics/models/yolo11n.onnx",
            "confidence": 0.65
        }
    }
}
```

> Полное описание всех опций (запись видео, пользовательские поля формы, телеметрия, настройка зон) доступно в [config/config.example.json](config/config.example.json) и в [Wiki](docs/wiki_ru.md).

---

## 📸 Скриншоты

<p align="center">
  <img src="docs/ru/images/Index.png" alt="Главная страница" width="85%">
</p>

<p align="center">
  <img src="docs/ru/images/CounterVideo.png" alt="Счётчик с видео и зоной" width="85%">
</p>

<p align="center">
  <img src="docs/ru/images/ReportsIndex.png" alt="Отчёты и аналитика" width="85%">
</p>

<details>
<summary><b>Показать остальные скриншоты (ещё 9)</b></summary>
<br>

| Описание | Скриншот |
|---|---|
| **Редактор зоны подсчёта** | <img src="docs/ru/images/CounterArea.png" alt="Настройка зоны подсчета"> |
| **Параметры камеры** | <img src="docs/ru/images/CounterModalSetting.png" alt="Настройка камеры"> |
| **Текстовый режим** | <img src="docs/ru/images/CounterText.png" alt="Счетчик с текстом"> |
| **Мульти-счётчики** | <img src="docs/ru/images/CounterMultiText.png" alt="Мульти счетчики"> |
| **Список отчётов счётчика** | <img src="docs/ru/images/ReportsItems.png" alt="Отчеты счетчика"> |
| **Просмотр отчёта** | <img src="docs/ru/images/ReportsItemShow.png" alt="Просмотр отчета"> |
| **Настройки системы** | <img src="docs/ru/images/Settings.png" alt="Настройки"> |
| **Информация о системе** | <img src="docs/ru/images/SystemInfo.png" alt="Системная информация"> |
| **Справка и документация** | <img src="docs/ru/images/Help.png" alt="Помощь"> |

</details>

---

## 👨‍💻 Автор

**Александр Киреев**

- Сайт: [bespredel.name](https://bespredel.name)
- Email: [hello@bespredel.name](mailto:hello@bespredel.name)
- GitHub: [@BespredeL](https://github.com/BespredeL)

---

## 🔗 Полезные ссылки

- Сайт проекта: [https://cvcounter.createdby.ru](https://cvcounter.createdby.ru)
- Документация (Wiki RU): [docs/wiki_ru.md](docs/wiki_ru.md)
- Руководство по мультиархитектурной платформе: [docs/multi_architecture_guide_ru.md](docs/multi_architecture_guide_ru.md)
- Описание API телеметрии: [docs/telemetry_api.md](docs/telemetry_api.md)
- Архитектуры и движки: [ONNX Runtime](https://onnxruntime.ai/) | [Ultralytics YOLO](https://github.com/ultralytics) | [Roboflow RF-DETR](https://github.com/roboflow/rf-detr) | [D-FINE](https://github.com/Peterande/D-FINE) | [OpenMMLab](https://github.com/open-mmlab/mmdetection)

---

## 📄 Лицензия

Проект распространяется под свободной лицензией **[GNU AGPLv3](LICENSE)**.

---

## ⭐ Поддержка

Если проект оказался для вас полезным, пожалуйста, поддержите его — поставьте **звезду ⭐** на GitHub!