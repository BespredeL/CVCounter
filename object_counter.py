# -*- coding: utf-8 -*-
# ! python3

# Developed by: Alexander Kireev
# Created: 01.11.2023
# Updated: 28.01.2024
# Website: https://bespredel.name


import time
import cv2
import numpy as np
from imutils.video import VideoStream
from ultralytics import YOLO
from shapely.geometry import Point, Polygon
from system.error_logger import ErrorLogger
from system.sort import Sort


class ObjectCounter:
    def __init__(self, location, socketio, config, **kwargs):
        # Load config
        config.read_config()
        detector_config = config.get("detections." + location)

        # Init config
        self.location = location
        self.socketio = socketio
        # self.location = kwargs.get('location')
        # self.socketio = kwargs.get('socketio')
        self.weights = kwargs.get('weights', detector_config.get('weights_path'))
        self.device = kwargs.get('device', detector_config.get('device', 'cpu'))
        self.confidence = kwargs.get('confidence', detector_config.get('confidence'))
        self.iou = kwargs.get('iou', detector_config.get('iou'))
        self.limits = kwargs.get('limits', detector_config.get('limits'))
        self.counting_area_color = kwargs.get('counting_area_color', detector_config.get('counting_area_color'))
        self.video_scale = detector_config.get('video_show_scale', config.get("detection_default.video_show_scale", 50))
        self.video_quality = detector_config.get('video_show_quality',
                                                 config.get("detection_default.video_show_quality", 50))
        self.indicator_size = detector_config.get('indicator_size', config.get("detection_default.indicator_size", 10))
        self.total_objects = []
        self.total_count = 0
        self.current_count = 0
        self.frame = None
        self.frame_lost = 0
        self.running = True
        self.paused = False

        # Init logger
        log_path = config.get("log_path")
        if self.location != '':
            log_path = f'error_{self.location}.log'
        self.logger = ErrorLogger(log_path)

        # Started counter value from config
        total_count = detector_config.get('start_total_count', 0)
        if total_count is not None and total_count > 0:
            self.total_count = int(total_count)
            self.total_objects = [item for item in range(-self.total_count, 0)]
            config.set("detections." + self.location + ".start_total_count", 0)
            config.save_config()

        # Video
        self.video_stream = kwargs.get('video_stream', detector_config['video_path'])
        if not self.video_stream.lower().startswith(('rtsp://', 'rtmp://', 'http://', 'https://', 'tcp://')):
            self.cap = self.video_stream
        else:
            self.cap = VideoStream(self.video_stream).start()

        # Model
        self.model = YOLO(self.weights)
        self.tracker = Sort(max_age=30, min_hits=3, iou_threshold=0.3)

        # DB
        self.DB = kwargs.get('db_client')

        # Set polygon
        self.polygon = Polygon(self.limits)

    """
    Reconnects to the video stream if the connection has been lost for more than N frames.

    Parameters:
        None

    Returns:
        None
    """

    def reconnect(self):
        self.frame = None
        self.frame_lost += 1
        if self.frame_lost > 10:
            self.frame_lost = 0
            # self.logger.log_error('Reconnect ' + self.location + '...')
            print(f'Reconnect {self.location}...')
            if self.socketio is not None:
                self.notification('Потеряно соединение с камерой!', 'danger')

            # if self.cap is not None:
            self.cap.stop()
            self.cap = None
            time.sleep(5)

            self.cap = VideoStream(self.video_stream).start()
            time.sleep(5)

    """
    Generates frames from a video stream.

    Args:
        model (optional): The model to be used for object detection. Defaults to None.
        video_stream (optional): The video stream to be used. Defaults to None.

    Returns:
        A generator that yields frames in the form of JPEG images.
    """

    def get_frames(self):
        self.frame_lost = 0
        while self.running:
            try:
                if self.frame is not None:
                    frame = self.frame
                else:
                    start_time = time.time()

                    frame = self.cap.read()
                    if frame is not None:
                        boxes = self.detect(frame)
                        frame = self.draw_counting_area(frame)
                        frame = self.detect_count(frame, boxes)
                        self.frame_lost = 0
                    else:
                        self.reconnect()
                        continue

                    end_time = time.time()
                    fps = 1 / np.round(end_time - start_time, 2)
                    cv2.putText(frame, f'FPS: {int(fps)}', (20, 70), cv2.FONT_HERSHEY_SIMPLEX,
                                1.5, (0, 0, 255), 2)

                scale_percent = int(self.video_scale)  # percent of original size
                width = int(frame.shape[1] * scale_percent / 100)
                height = int(frame.shape[0] * scale_percent / 100)
                frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)

                ret, frame = cv2.imencode('.jpg', frame,
                                          [cv2.IMWRITE_JPEG_QUALITY, int(self.video_quality)])

                frame = frame.tobytes()

                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            except Exception as e:
                print(e)

    """
    Run the generation of frames.

    Parameters:
        self (object): The instance of the class.

    Returns:
        None
    """

    def gen_frames_run(self):
        while self.running:
            try:
                start_time = time.time()

                frame = self.cap.read()
                if frame is not None:
                    boxes = self.detect(frame)
                    frame = self.draw_counting_area(frame)
                    frame = self.detect_count(frame, boxes)
                    self.frame_lost = 0
                else:
                    self.reconnect()
                    continue

                end_time = time.time()
                fps = 1 / np.round(end_time - start_time, 2)
                cv2.putText(frame, f'FPS: {int(fps)}', (20, 70), cv2.FONT_HERSHEY_SIMPLEX,
                            1.5, (0, 0, 255), 2)

                self.frame = frame
            except Exception as e:
                print(e)
                self.reconnect()

    """
    Counts the number of runs in the video stream.

    Parameters:
        self (object): The instance of the class.

    Returns:
        None
    """

    def count_run(self):
        while self.running:
            try:
                frame = self.cap.read()
                if frame is None:
                    self.reconnect()
                    continue

                boxes = self.detect(frame)
                self.detect_count(frame, boxes)

            except Exception as e:
                print(e)
                self.reconnect()

    """
    Detects objects in an image using a pre-trained model.

    Parameters:
        image (ndarray): The input image as a numpy array.

    Returns:
        ndarray: An array of updated results after tracking the detected objects.
    """

    def detect(self, image):
        results = self.model.predict(
            image,
            conf=self.confidence,
            iou=self.iou,
            device=self.device,
            # stream_buffer=False,
            # stream=True
        )

        xyxy = results[0].boxes.xyxy.cpu().numpy()
        conf = results[0].boxes.conf.cpu().numpy()
        detections = np.concatenate((xyxy, conf.reshape(-1, 1)), axis=1)

        return self.tracker.update(detections)

    """
    Draws a counting area on the given image.

    Parameters:
        image (numpy.ndarray): The image on which the counting area should be drawn.

    Returns:
        numpy.ndarray: The image with the counting area drawn on it.
    """

    def draw_counting_area(self, image):
        alpha = 0.4
        overlay = image.copy()

        # Polygon corner points coordinates
        pts = np.array(self.limits, np.int32)
        pts = pts.reshape((-1, 1, 2))
        cv2.fillPoly(overlay, [pts], self.counting_area_color)

        return cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0)

    """
    Detects objects on an image and returns the image.

    Parameters:
        image (numpy.ndarray): The image on which the boxes will be drawn.
        boxes (List[Tuple[int]]): A list of boxes, where each box is represented by a tuple of (x1, y1, x2, y2, rid),
                                  where x1, y1 are the top-left coordinates, x2, y2 are the bottom-right coordinates,
                                  and rid is the ID of the box.

    Returns:
        numpy.ndarray: The modified image with the boxes drawn on it.
    """

    def detect_count(self, image, boxes):
        if self.paused:
            return image

        for result in boxes:
            x1, y1, x2, y2, rid = result
            x1, y1, x2, y2 = map(int, result[:4])
            w, h = x2 - x1, y2 - y1
            cx, cy = x1 + w // 2, y1 + h // 2
            cv2.circle(image, (cx, cy), int(self.indicator_size), (255, 0, 255), cv2.FILLED)
            if self.total_objects.count(rid) != 0:
                cv2.circle(image, (cx, cy), int(self.indicator_size), (0, 255, 0), cv2.FILLED)

            # Определяем точку
            point = Point(cx, cy)
            if point.within(self.polygon) and self.total_objects.count(rid) == 0:
                self.total_objects.append(rid)
                self.current_count += 1
            self.total_count = len(self.total_objects)

        if self.socketio is not None:
            self.socketio.emit(f'{self.location}_count', {'total': self.total_count, 'current': self.current_count})

        return image

    """
    Save count.

    Returns:
        dict: The total, defect and correct count.
    """

    def save_count(self, location, name, correct_count, defect_count, active=1):
        total_count = int(self.total_count)
        defect_count = int(defect_count)
        correct_count = int(correct_count)
        item_count = str(total_count - defect_count + correct_count)
        result = self.DB.save_result(
            location=location,
            name=name,
            item_count=item_count,
            source_count=total_count,
            correct_count=correct_count,
            defects_count=defect_count,
            active=active
        )

        if result:
            # self.total_objects = []
            # self.total_count = 0
            # self.current_count = 0
            self.notification('Успешно сохранено!', 'success')
        else:
            self.notification('Ошибка сохранения!', 'danger')

        return dict(total=total_count, defect=defect_count, correct=correct_count)

    """
    Resets the count of total objects and total count.

    Parameters:
        self (object): The instance of the class.

    Returns:
        None
    """

    def reset_count(self, location):
        self.total_objects = []
        self.total_count = 0
        self.current_count = 0

        self.DB.close_current_count(location)

        self.notification('Подсчет успешно завершен!', 'primary')

    """
    Reset the current count.

    Parameters:
        None

    Returns:
        None
    """

    def reset_count_current(self, location, name, correct_count, defect_count):
        current_count = int(self.current_count)
        total_count = int(self.total_count)
        defect_count = int(defect_count)
        correct_count = int(correct_count)
        try:
            self.DB.save_part_result(
                location=location,
                name=name,
                current_count=current_count,
                total_count=total_count,
                defects_count=defect_count,
                correct_count=correct_count
            )
        except Exception as e:
            print(e)

        self.current_count = 0

        if self.socketio is not None:
            self.socketio.emit(f'{location}_count', {'total': total_count, 'current': 0})
            self.notification('Счетчик сброшен!', 'primary')

    """
    Emit a notification to the client.

    Parameters:
        message (str): The message to be displayed.
        type (str): The type of notification (success, danger, warning, info, primary, secondary).

    Returns:
        None
    """

    def notification(self, message='', type='primary'):
        if self.socketio is not None:
            self.socketio.emit(f'{self.location}_notification', {'type': type, 'message': message})

    """
    Start counting.

    Parameters:
        None

    Returns:
        None
    """

    def start(self):
        # self.running = True
        if self.socketio is not None and self.paused is True:
            self.notification('Подсчет запущен!', 'primary')
        self.paused = False

    """
    Stop counting and the thread.

    Parameters:
        None

    Returns:
        None
    """

    def stop(self):
        if self.socketio is not None and self.running is True:
            self.notification('Подсчет остановлен!', 'primary')
        self.running = False

    """
    Pause counting.

    Parameters:
        None

    Returns:
        None
    """

    def pause(self):
        if self.socketio is not None and self.paused is False:
            self.notification('Подсчет приостановлен!', 'primary')
        self.paused = True

    """
    Is Paused.

    Parameters:
        None

    Returns:
        None
    """

    def is_pause(self):
        return self.paused
