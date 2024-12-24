# CVCounter

[![Readme EN](https://img.shields.io/badge/README-EN-blue.svg)](https://github.com/BespredeL/CVCounter/blob/master/README_EN.md)
[![Readme RU](https://img.shields.io/badge/README-RU-blue.svg)](https://github.com/BespredeL/CVCounter/blob/master/README.md)
[![GitHub license](https://img.shields.io/badge/license-AGPL--3.0-458a7b.svg)](https://github.com/BespredeL/CVCounter/blob/master/LICENSE)

CVCounter - это приложение для подсчета объектов с использованием компьютерного зрения, реализованное на Python с использованием Flask.
Проект предоставляет три режима отображения данных: основной вид с видео, текстовый вид и текстовый вид с двумя счетчиками.

---

## Установка

1. **Клонируйте репозиторий:**
   ```bash
   git clone https://github.com/BespredeL/CVCounter.git
   ```
2. **Перейдите в директорию проекта:**
   ```bash
   cd CVCounter
   ```
3. **Установите virtual environment:**
   ```bash
   python3 -m venv venv
   ```
4. **Активируйте virtual environment:**
   ```bash
   source venv/bin/activate
   ```
5. **Установите зависимости:**
   ```bash
   pip3 install -r requirements.txt
   ```
6. **Переименуйте файл конфигурации:**
   ```bash
   mv config.example.json config.json
   ```
7. **Измените параметры в файле конфигурации, добавьте свою модель YOLO.**
8. **Запустите приложение:**
   ```bash
   python app.py
   ```

---

## Использование

**В этом решение реализовано 3 вида просмотра:**

1. **Основной вид** - страница на которой выводится значение счетчиков и видео с результатом распознавания
2. **Текстовый вид** - страница на которой выводится только значение счетчиков
3. **Текстовый вид с двумя счетчиками** - страница на которой выводится значение 2 счетчиков (например на входе и выходе)

После нескольких вариантов, принял решение реализации на Flask, т.е решение в виде мини веб-сайта,
так как такое решение позволяет избежать установки какого либо дополнительного софта на клиенты.
А так же это решение не требовательно к клиентам в плане потребления ресурсов (за исключением основного вида с видео)

Мне удалось запустить 6 одновременных подсчетов (без вывода видео), и 5 подсчета с выводом видео.<br>

Характеристики сервера:

- AMD Ryzen 5 3600
- GeForce GTX 1050 Ti (4Гб)

Вы можете запускать браузер в режиме киоска, для предотвращения выхода из него (например для Google Chrome при запуске можно указать "
--kiosk --start-fullscreen")

**P.S.:**

- Друзья, если вас не затруднит, не убирайте, пожалуйста, мой копирайт внизу страницы. Вам это ничего не стоит, а мне приятно.
- Всё это реализовано без какого либо ТЗ и никто не верил в успех, поэтому пока что есть некоторая хаотичность, но постараюсь всё переделать
  более правильно =)
- Если вам помогло это решение, вы можете проспонсировать меня отправив слово "Спасибо". Ссылки на контакты ниже =)
- Если нужна помощь с внедрением, можем обсудить =).

---

## Конфигурация

```json5
{
    "general": {
        "debug": true,
        // включить режим отладки
        "log_path": "errors.log",
        // путь к файлу журнала
        "default_language": "ru",
        // язык по умолчанию
        "allow_unsafe_werkzeug": false,
        // разрешить небезопасные операции в werkzeug
        "button_change_theme": true,
        // показать кнопку изменения темы
        "button_fullscreen": true,
        // показать кнопку перехода в полноэкранный режим
        "button_backward": false,
        // показать кнопку назад
        "collapsed_keyboard": true
        // показать клавиатуры свернутыми
    },
    "server": {
        "host": "0.0.0.0",
        // адрес сервера
        "port": 80,
        // порт сервера
        "use_reloader": false,
        // включить режим перезагрузки
        "log_output": true,
        // включить вывод журнала
        "socketio_key": ""
        // socketio ключ
    },
    "users": {
        // логин:пароль по умолчанию admin:admin
        "admin": "scrypt:32768:8:1$rsdPYhqaQqpXQQ0o$aa3359c86228b4cee5fe8c4ed694db4b371fa7fab5100fa7b446db7e1ed8077e3bb63228d4a1899aeeef9b8d15f8e8bdbcc3457f020bcb3ec320332c76b5896b"
        // логин:пароль
    },
    "db": {
        "uri": "sqlite:///system/database.db",
        // подключение к базе данных
        "prefix": ""
        // префикс таблиц
    },
    "form": {
        // конфигурация форм
        "defect_show": true,
        // показать форму брака
        "correct_show": true,
        // показать форму коррекции
        "custom_fields": {
            // конфигурация пользовательских полей
            "field_one": {
                "name": "field_one",
                // название поля
                "label": "Field One",
                // подпись поля
                "type": "text"
                // тип поля
            }
        }
    },
    "detection_default": {
        // конфигурация обнаружения по умолчанию
        "video_path": "",
        // путь к видеофайлу или источнику камеры
        "video_show_scale": 50,
        // масштаб вывода видео на странице
        "video_show_quality": 50,
        // качество вывода видео на странице
        "video_fps": false,
        // ручная установка FPS
        "weights_path": "yolo_cfg/models/yolov8n.pt",
        // путь к модели Yolov8
        "counting_area": [
            [
                0,
                0
            ],
            [
                100,
                0
            ],
            [
                100,
                100
            ],
            [
                0,
                100
            ]
        ],
        // площадь подсчета (многоугольник)
        "confidence": 0.7,
        // порог доверия
        "iou": 0.7,
        // порог iou
        "device": 0,
        // указывает вычислительное устройство(а) для обучения (смотрите документацию ultralytics)
        "vid_stride": 1,
        // шаг видеопотока
        "indicator_size": 10,
        // размер индикатора
        "counting_area_color": [
            67,
            211,
            255
        ],
        // цвет зоны подсчета
        "classes": {}
        // классы (объекты) для обнаружения (оставьте пустым для всех классов)
    },
    "detections": {
        // конфигурации обнаружения
        "ExampleCam": {
            // Наименование подсчета (используется в адресе страницы, должно быть на латинице)
            "label": "Label ExampleCam",
            // Наименование подсчета (используется для вывода на страницах)
            "start_total_count": 0,
            // Число с которого начинается подсчет (по умолчанию 0, но если необходимо начать с какого-то числа, то можно указать)
            "video_path": "",
            // путь к видеофайлу или источнику камеры
            "video_show_scale": 70,
            // масштаб вывода видео на странице
            "video_show_quality": 30,
            // качество вывода видео на странице
            "video_fps": 30,
            // ручная установка FPS (необязательно)
            "weights_path": "yolo_cfg/models/yolov8n.pt",
            // путь к модели Yolov8
            "counting_area": [
                [
                    0,
                    0
                ],
                [
                    100,
                    0
                ],
                [
                    100,
                    100
                ],
                [
                    0,
                    100
                ]
            ],
            // площадь подсчета (многоугольник)
            "confidence": 0.7,
            // порог доверия
            "iou": 0.7,
            // порог iou
            "device": 0,
            // указывает вычислительное устройство(а) для обучения (смотрите документацию ultralytics)
            "vid_stride": 1,
            // шаг видеопотока
            "indicator_size": 10,
            // размер индикатора
            "counting_area_color": [
                255,
                64,
                0
            ],
            // цвет зоны подсчета
            "classes": {},
            // классы (объекты) для обнаружения (оставьте пустым для всех классов)
            "dataset_create": {
                // автоматическое создание набора данных
                "enable": true,
                // включить создание набора данных
                "probability": 0.05,
                // вероятность создания изображения набора данных (число от 0.01 до 1, где 0.01 - 1% и 1 - 100%)
                "path": "yolo_cfg/saved_images/ExampleCam"
                // путь для сохранения набора данных
            }
        },
    }
}
```

---

## Скриншоты

<img src="https://github.com/BespredeL/BespredeL/blob/9b1aa0d2a841c04fce5a0cf58453f6cd5c831a88/VideoView.gif" alt="">
<img src="https://github.com/BespredeL/BespredeL/blob/da1fce84f2e64f149142a7302a98a7e5e06f62fa/IndexPage.png" alt="">
<img src="https://github.com/BespredeL/BespredeL/blob/da1fce84f2e64f149142a7302a98a7e5e06f62fa/VideoView.png" alt="">
<img src="https://github.com/BespredeL/BespredeL/blob/da1fce84f2e64f149142a7302a98a7e5e06f62fa/TextView.png" alt="">
<img src="https://github.com/BespredeL/BespredeL/blob/da1fce84f2e64f149142a7302a98a7e5e06f62fa/MultiTextView.png" alt="">
P.S.: Не лучший пример на скриншотах. Не нашел ничего лучше, чем камера в открытом доступе (((

---

## Автор

Александр Киреев

Website: [https://bespredel.name](https://bespredel.name)<br>
E-mail: [hello@bespredel.name](mailto:hello@bespredel.name)<br>
Telegram: [https://t.me/BespredeL_name](https://t.me/BespredeL_name)

---

## Ссылки

Ultralytics: [https://github.com/ultralytics](https://github.com/ultralytics)

---

## Лицензия

**AGPL-3.0 License**: Эта [OSI-approved](https://opensource.org/licenses/) лицензия с открытым исходным кодом идеально подходит для
студентов и энтузиастов, способствуя открытому сотрудничеству и обмену знаниями.