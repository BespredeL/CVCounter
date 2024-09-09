## <div align="center">CVCounter</div>
Данное решение далеко от идела, даже наверно вообще кусок ..., но оно рабочее =))
Это мой первый опыт работы с Python, поэтому получилось как получилось.


**В этом решение реализовано 3 вида просмотра:**
1. **Основной вид** - страница на которой выводится значение счетчиков и видео с результатом распознавания
2. **Текстовый вид** - страница на которой выводится только значение счетчиков
3. **Текстовый вид с двумя счетчиками** - страница на которой выводится значение 2 счетчиков (например на входе и выходе)

После нескольких вариантов, принял решение реализации на Flask, т.е решение в виде мини веб-сайта,
так как такое решение позволяет избежать установки какого либо дополнительного софта на клиенты.
А так же это решение не требовательно к клиентам в плане ресурсов (за исключением основного вида с видео)

Мне удалось запустить 5 одновременных подсчетов (без вывода видео), и 4 подсчета с выводом видео.<br>

Характеристики сервера:
- AMD Ryzen 5 3600
- GeForce GTX 1050 Ti (4Гб)

Все основные настройки находятся в файле config.json (переименуйте config.example.json в config.json)

**P.S.:** 
- Друзья, если вас не затруднит, не убирайте, пожалуйста, мой копирайт внизу страницы. Это не требование, но если оставите я буду очень вам благодарен! 
- Всё это реализовано без какого либо ТЗ и вообще никто не верил в успех, поэтому пока что есть некоторая хаотичность, но постараюсь всё переделать более правильно =)
- Если вам помогло это решение, вы можете проспонсировать меня отправив слово "Спасибо". Ссылки на контакты ниже =))
- Если нужна помощь с внедрением, можем обсудить =).

## Config
```json5
{
  "general": {
    "debug": true, // включить режим отладки
    "log_path": "errors.log", // путь к файлу журнала
    "default_language": "ru", // язык по умолчанию
    "allow_unsafe_werkzeug": false, // разрешить небезопасные операции в werkzeug
    "button_change_theme": true, // показать кнопку изменения темы
    "button_fullscreen": true, // показать кнопку перехода в полноэкранный режим
    "button_backward": false // показать кнопку назад
  },
  "server": {
    "host": "0.0.0.0", // адрес сервера
    "port": 80, // порт сервера
    "threaded": true, // включить многопоточный режим
    "use_reloader": false, // включить режим перезагрузки
    "log_output": true, // включить вывод журнала
    "socketio_key": "" // socketio ключ
  },
  "users": {
    // логин:пароль по умолчанию admin:admin
    "admin": "scrypt:32768:8:1$rsdPYhqaQqpXQQ0o$aa3359c86228b4cee5fe8c4ed694db4b371fa7fab5100fa7b446db7e1ed8077e3bb63228d4a1899aeeef9b8d15f8e8bdbcc3457f020bcb3ec320332c76b5896b" // логин:пароль
  },
  "db": {
    "host": "localhost", // хост базы данных
    "user": "", // пользователь базы данных
    "password": "", // пароль базы данных
    "database": "", // имя базы данных
    "prefix": "" // префикс таблицы базы данных
  },
  "detection_default": { // конфигурация обнаружения по умолчанию
    "video_path": "", // путь к видеофайлу или источнику камеры
    "video_show_scale": 50, // масштаб вывода видео на странице
    "video_show_quality": 50, // качество вывода видео на странице
    "weights_path": "yolo_cfg/models/yolov8n.pt", // путь к модели Yolov8
    "counting_area": [[0, 0], [100, 0], [100, 100], [0, 100]], // площадь подсчета (многоугольник)
    "confidence": 0.7, // порог доверия
    "iou": 0.7, // порог iou
    "device": 0, // указывает вычислительное устройство(а) для обучения (смотрите документацию ultralytics)
    "vid_stride": 1, // шаг видеопотока
    "indicator_size": 10, // размер индикатора
    "counting_area_color": [67, 211, 255], // цвет зоны подсчета
    "classes": {} // классы (объекты) для обнаружения (оставьте пустым для всех классов)
  },
  "detections": { // конфигурации обнаружения
    "ExampleCam": { // Наименование подсчета (используется в адресе страницы, должно быть на латинице)
      "label": "Label ExampleCam", // Наименование подсчета (используется для вывода на страницах)
      "start_total_count": 0, // Число с которого начинается подсчет (по умолчанию 0, но если необходимо начать с какого-то числа, то можно указать)
      "video_path": "", // путь к видеофайлу или источнику камеры
      "video_show_scale": 70, // масштаб вывода видео на странице
      "video_show_quality": 30, // качество вывода видео на странице
      "weights_path": "yolo_cfg/models/yolov8n.pt", // путь к модели Yolov8
      "counting_area": [[0, 0], [100, 0], [100, 100], [0, 100]], // площадь подсчета (многоугольник)
      "confidence": 0.7, // порог доверия
      "iou": 0.7, // порог iou
      "device": 0, // указывает вычислительное устройство(а) для обучения (смотрите документацию ultralytics)
      "vid_stride": 1, // шаг видеопотока
      "indicator_size": 10, // размер индикатора
      "counting_area_color": [255, 64, 0], // цвет зоны подсчета
      "classes": {}, // классы (объекты) для обнаружения (оставьте пустым для всех классов)
      "dataset_create": { // автоматическое создание набора данных
        "enable": true, // включить создание набора данных
        "probability": 0.05, // вероятность создания изображения набора данных (число от 0.01 до 1, где 0.01 - 1% и 1 - 100%)
        "path": "yolo_cfg/saved_images/ExampleCam" // путь для сохранения набора данных
      }
    },
  }
}
```

## <div align="center">Screenshots</div>
<img src="https://github.com/BespredeL/BespredeL/blob/9b1aa0d2a841c04fce5a0cf58453f6cd5c831a88/VideoView.gif" alt="">
<img src="https://github.com/BespredeL/BespredeL/blob/da1fce84f2e64f149142a7302a98a7e5e06f62fa/IndexPage.png" alt="">
<img src="https://github.com/BespredeL/BespredeL/blob/da1fce84f2e64f149142a7302a98a7e5e06f62fa/VideoView.png" alt="">
<img src="https://github.com/BespredeL/BespredeL/blob/da1fce84f2e64f149142a7302a98a7e5e06f62fa/TextView.png" alt="">
<img src="https://github.com/BespredeL/BespredeL/blob/da1fce84f2e64f149142a7302a98a7e5e06f62fa/MultiTextView.png" alt="">
P.S.: Не лучший пример на скриншотах. Не нашел ничего лучше, чем камера в открытом доступе (((

## <div align="center">Author</div>

Александр Киреев

Website: [https://bespredel.name](https://bespredel.name)<br>
E-mail: [hello@bespredel.name](mailto:hello@bespredel.name)<br>
Telegram: [https://t.me/BespredeL_name](https://t.me/BespredeL_name)

## <div align="center">References</div>
Ultralytics: [https://github.com/ultralytics](https://github.com/ultralytics)

## <div align="center">License</div>
**AGPL-3.0 License**: This [OSI-approved](https://opensource.org/licenses/) open-source license is ideal for students and enthusiasts,
  promoting open collaboration and knowledge sharing.