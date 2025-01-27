# CVCounter

[![Readme EN](https://img.shields.io/badge/README-EN-blue.svg)](https://github.com/BespredeL/CVCounter/blob/master/README_EN.md)
[![Readme RU](https://img.shields.io/badge/README-RU-blue.svg)](https://github.com/BespredeL/CVCounter/blob/master/README.md)
[![GitHub license](https://img.shields.io/badge/license-AGPL--3.0-458a7b.svg)](https://github.com/BespredeL/CVCounter/blob/master/LICENSE)

CVCounter is an object counting application using computer vision, implemented in Python with Flask. The project provides three modes of
data display: main view with video, text view, and text view with two counters.

---

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/BespredeL/CVCounter.git
   ```
2. **Navigate to the project directory:**
   ```bash
   cd CVCounter
   ```
3. **Install virtual environment:**
   ```bash
   python3 -m venv venv
   ```
4. **Activate virtual environment:**
   ```bash
   source venv/bin/activate
   ```
5. **Install dependencies:**
   ```bash
   pip3 install -r requirements.txt
   ```
6. **Rename the configuration file:**
   ```bash
   mv config.example.json config.json
   ```
7. **Change the parameters in the configuration file, add your YOLO model.**
8. **Run the application:**
   ```bash
   python app.py
   ```

---

## Usage

**This solution implements 3 types of views:**

1. **Main view** - a page displaying the counter values and a video with recognition results
2. **Text view** - a page displaying only the counter values
3. **Text view with two counters** - a page displaying the values of 2 counters (e.g., at the input and output)

After several options, I decided to implement it with Flask, i.e., as a mini website solution, as it allows avoiding the installation of any
additional software on clients. Moreover, this solution is not resource-intensive for clients (except for the main view with video).

I managed to run 6 simultaneous counts (without video output), and 5 counts with video output.

Server specifications:

- AMD Ryzen 5 3600
- GeForce GTX 1050 Ti (4GB)

You can run the browser in kiosk mode to prevent exiting it (for example, for Google Chrome, you can specify "--kiosk --start-fullscreen" at
startup).

**P.S.:**

- Friends, if you don't mind, please don't remove my copyright at the bottom of the page. It doesn't cost you anything, but it makes me
  happy.
- All of this was implemented without any specifications and nobody believed in success, so there is currently some chaos, but I will try to
  redo everything more correctly =)
- If this solution helped you, you can sponsor me by sending the word "Thanks". Contact details are below =)
- If you need help with the implementation, we can discuss it =).

---

## Configuration

```json5
{
    "general": {
        "debug": true,
        // enable debug mode
        "log_path": "errors.log",
        // path to log file
        "default_language": "ru",
        // default language
        "allow_unsafe_werkzeug": false,
        // allow unsafe operations in werkzeug
        "button_change_theme": true,
        // show button changing theme
        "button_fullscreen": true,
        // show button fullscreen
        "button_backward": false,
        // show back button
        "button_save_capture": false,
        // show save capture button
        "collapsed_keyboard": true
        // show collapsed keyboard
    },
    "server": {
        "host": "0.0.0.0",
        // server host
        "port": 80,
        // server port
        "use_reloader": false,
        // enable reloader mode
        "log_output": true,
        // enable log output
        "socketio_key": ""
        // socketio key
    },
    "users": {
        // login:password default admin:admin
        "admin": "scrypt:32768:8:1$rsdPYhqaQqpXQQ0o$aa3359c86228b4cee5fe8c4ed694db4b371fa7fab5100fa7b446db7e1ed8077e3bb63228d4a1899aeeef9b8d15f8e8bdbcc3457f020bcb3ec320332c76b5896b"
        // login:password
    },
    "db": {
        "uri": "sqlite:///system/database.db",
        // database connection
        "prefix": ""
        // table prefix
    },
    "form": {
        // form configuration
        "defect_show": true,
        // show defect form
        "correct_show": true,
        // show correction form
        "custom_fields": {
            // custom fields configuration
            "field_one": {
                "name": "field_one",
                // field name
                "label": "Field One",
                // field signature
                "type": "text"
                // field type
            }
        }
    },
    "detection_default": {
        "video_show_scale": 50,
        // scale of video preview
        "video_show_quality": 50,
        // quality of video preview
        "video_fps": 0,
        // manual FPS setting (0 - automatic installation)
        "model_type": "yolo",
        // model type (default yolo)
        "weights_path": "yolo_cfg/models/yolov8n.pt",
        // path to model Yolov8
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
        // counting area polygon
        "confidence": 0.7,
        // confidence threshold
        "iou": 0.7,
        // iou threshold
        "device": 0,
        // specifies the computing device(s) for training (see ultralytics documentation)
        "vid_stride": 1,
        // video stream stride
        "indicator_size": 10,
        // size of indicator
        "counting_area_color": [
            67,
            211,
            255
        ],
        // color of counting area
        "classes": {}
        // classes to detect (leave empty for all classes)
    },
    "detections": {
        // detection configs
        "ExampleCam": {
            // name
            "label": "Label ExampleCam",
            // label
            "start_total_count": 0,
            // start total count
            "video_path": "",
            // path to video file or camera src
            "video_show_scale": 70,
            // scale of video preview
            "video_show_quality": 30,
            // quality of video preview
            "video_fps": false,
            // manual FPS setting (optional)
            "model_type": "yolo",
            // model type (default yolo)
            "weights_path": "yolo_cfg/models/yolov8n.pt",
            // path to model Yolov8
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
            // counting area polygon
            "confidence": 0.7,
            // confidence threshold
            "iou": 0.7,
            // iou threshold
            "device": 0,
            // specifies the computing device(s) for training (see ultralytics documentation)
            "vid_stride": 1,
            // video stream stride
            "indicator_size": 10,
            // size of indicator
            "counting_area_color": [
                255,
                64,
                0
            ],
            // color of counting area
            "classes": {},
            // classes to detect (leave empty for all classes)
            "dataset_create": {
                // automatic dataset creation
                "enable": true,
                // enable dataset creation
                "probability": 0.05,
                // probability of creating a dataset image (number from 0.01 to 1, where 0.01 is 1% and 1 is 100%)
                "path": "yolo_cfg/saved_images/ExampleCam"
                // path for saving dataset
            }
        },
    }
}
```

---

## Screenshots

<img src="https://github.com/BespredeL/BespredeL/blob/9b1aa0d2a841c04fce5a0cf58453f6cd5c831a88/VideoView.gif" alt="">
<img src="https://github.com/BespredeL/BespredeL/blob/da1fce84f2e64f149142a7302a98a7e5e06f62fa/IndexPage.png" alt="">
<img src="https://github.com/BespredeL/BespredeL/blob/da1fce84f2e64f149142a7302a98a7e5e06f62fa/VideoView.png" alt="">
<img src="https://github.com/BespredeL/BespredeL/blob/da1fce84f2e64f149142a7302a98a7e5e06f62fa/TextView.png" alt="">
<img src="https://github.com/BespredeL/BespredeL/blob/da1fce84f2e64f149142a7302a98a7e5e06f62fa/MultiTextView.png" alt="">
P.S.: Not the best example in the screenshots. Couldn't find anything better than an open-access camera (((

---

## Author

Aleksandr Kireev

Website: [https://bespredel.name](https://bespredel.name)<br>
E-mail:  [hello@bespredel.name](mailto:hello@bespredel.name)<br>
GitHub:  [https://github.com/BespredeL](https://github.com/BespredeL)

---

## Links

Ultralytics: [https://github.com/ultralytics](https://github.com/ultralytics)

---

## License

**AGPL-3.0 License**: This [OSI-approved](https://opensource.org/licenses/) open-source license is ideal for students and enthusiasts,
promoting open collaboration and knowledge sharing.