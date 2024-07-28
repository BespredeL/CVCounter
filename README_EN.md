## <div align="center">CVCounter</div>
This solution is far from ideal, probably just a piece of ..., but it works =)<br> 
This is my first experience working with Python, so it turned out the way it did.

This solution implements 2 types of views:

1. **Main view** - a page displaying the counter values and a video with recognition results
2. **Text view** - a page displaying only the counter values
3. **Text view with two counters** - a page on which the value of 2 counters is displayed (for example, at the input and output)

After several options, I decided to implement it with Flask, i.e. as a mini website solution, 
as it allows to avoid installing any additional software on the clients. 
Moreover, this solution is not resource-intensive for clients (except for the main view with video)

I managed to run 5 simultaneous counts (without video output), and 4 counts with video output.

Server specifications:

AMD Ryzen 5 3600
- GeForce GTX 1050 Ti (4GB)
- All main settings are located in the config.json file (rename config.example.json to config.json)

P.S.:
- Friends, if you don't mind, please don't remove my copyright at the bottom of the page. It's not a requirement, but if you leave it, I'll be very grateful to you!
- All of this was implemented without any specifications and nobody believed in success, so there is currently some chaos, but I will try to redo everything more correctly =)
- If this solution helped you, you can sponsor me by sending the word "Thanks". Contact details are below =))
- If you need help with the implementation, we can discuss it =).

## Config
```json5
{
  "general": {
    "debug": true, // enable debug mode
    "log_path": "errors.log", // path to log file
    "default_language": "ru" // default language
  },
  "server": {
    "host": "0.0.0.0", // server host
    "port": 80, // server port
    "threaded": true, // enable threaded mode
    "use_reloader": false, // enable reloader mode
    "log_output": true, // enable log output
    "socketio_key": "" // socketio key
  },
  "db": {
    "host": "localhost", // database host
    "user": "", // database user
    "password": "", // database password
    "database": "", // database name
    "prefix": "" // database table prefix
  },
  "detection_default": { // default detection config
    "video_path": "", // path to video file or camera src
    "video_show_scale": 50, // scale of video preview
    "video_show_quality": 50, // quality of video preview
    "weights_path": "yolo_cfg/models/yolov8n.pt", // path to model Yolov8
    "counting_area": [[0, 0], [100, 0], [100, 100], [0, 100]], // counting area polygon
    "confidence": 0.7, // confidence threshold
    "iou": 0.7, // iou threshold
    "device": 0, // specifies the computing device(s) for training (see ultralytics documentation)
    "vid_stride": 1, // video stream stride
    "indicator_size": 10, // size of indicator
    "counting_area_color": [67, 211, 255], // color of counting area
    "classes": {} // classes to detect (leave empty for all classes)
  },
  "detections": { // detection configs
    "ExampleCam": { // name
      "label": "Label ExampleCam", // label
      "start_total_count": 0, // start total count
      "video_path": "", // path to video file or camera src
      "video_show_scale": 70, // scale of video preview
      "video_show_quality": 30, // quality of video preview
      "weights_path": "yolo_cfg/models/yolov8n.pt", // path to model Yolov8
      "counting_area": [[0, 0], [100, 0], [100, 100], [0, 100]], // counting area polygon
      "confidence": 0.7, // confidence threshold
      "iou": 0.7, // iou threshold
      "device": 0, // specifies the computing device(s) for training (see ultralytics documentation)
      "vid_stride": 1, // video stream stride
      "indicator_size": 10, // size of indicator
      "counting_area_color": [255, 64, 0], // color of counting area
      "classes": {}, // classes to detect (leave empty for all classes)
      "dataset_create": { // automatic dataset creation
        "enable": true, // enable dataset create
        "probability": 0.05, // probability of creating an image of a dataset (a number from 0.01 to 1, where 0.01 is 1% and 1 is 100%)
        "path": "yolo_cfg/saved_images/ExampleCam" // path to save dataset
      }
    },
  }
}
```

## <div align="center">Screenshots</div>
<img src="https://github.com/BespredeL/BespredeL/blob/c27b6d786e6569cbaa17d49eac8c7433812a1024/Desktop-2023.12.31-13.16.42.01.gif" alt="" width="360">
<img src="https://github.com/BespredeL/BespredeL/blob/c27b6d786e6569cbaa17d49eac8c7433812a1024/Main%20View.png" alt="" width="360">
<img src="https://github.com/BespredeL/BespredeL/blob/c27b6d786e6569cbaa17d49eac8c7433812a1024/Text%20View.png" alt="" width="360">

## <div align="center">Author</div>

Aleksandr Kireev

Website: [https://bespredel.name](https://bespredel.name)<br>
E-mail: [hello@bespredel.name](mailto:hello@bespredel.name)<br>
Telegram: [https://t.me/BespredeL_name](https://t.me/BespredeL_name)

## <div align="center">References</div>
Ultralytics: [https://github.com/ultralytics](https://github.com/ultralytics)

## <div align="center">License</div>
**AGPL-3.0 License**: This [OSI-approved](https://opensource.org/licenses/) open-source license is ideal for students and enthusiasts,
  promoting open collaboration and knowledge sharing.