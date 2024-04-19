# -*- coding: utf-8 -*-
# ! python3

# Developed by: Alexander Kireev
# Created: 01.11.2023
# Updated: 19.04.2024
# Website: https://bespredel.name

import os
import random
import re
import time
import cv2
import numpy as np
from shapely.geometry import Point, Polygon
from ultralytics import YOLO, settings
from system.error_logger import ErrorLogger
from system.sort import Sort
from system.translate import trans
from system.video_stream_manager import VideoStreamManager


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
        self.confidence = kwargs.get('confidence',
                                     detector_config.get('confidence', config.get('detection_default.confidence', 0.5)))
        self.iou = kwargs.get('iou', detector_config.get('iou', config.get('detection_default.iou', 0.7)))
        self.counting_area = kwargs.get('counting_area', detector_config.get('counting_area'))
        self.counting_area_color = kwargs.get('counting_area_color', detector_config.get('counting_area_color'))
        self.video_scale = detector_config.get('video_show_scale', config.get("detection_default.video_show_scale", 50))
        self.video_quality = detector_config.get('video_show_quality',
                                                 config.get("detection_default.video_show_quality", 50))
        self.indicator_size = detector_config.get('indicator_size', config.get("detection_default.indicator_size", 10))
        self.vid_stride = detector_config.get('vid_stride', config.get("detection_default.vid_stride", 1))
        self.classes = detector_config.get('classes', {})
        self.dataset = detector_config.get('dataset_create', {})

        # Init variables
        self.total_objects = []
        self.total_count = 0
        self.current_count = 0
        self.frame = None
        self.frame_lost = 0
        self.running = True
        self.paused = False

        # Init logger
        log_path = config.get("general.log_path")
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
        # if not self.video_stream.lower().startswith(('rtsp://', 'rtmp://', 'http://', 'https://', 'tcp://')):
        #     self.cap = self.video_stream
        # else:
        #     self.cap = VideoStream(self.video_stream).start()
        self.vsm = VideoStreamManager(self.video_stream)
        self.vsm.start()

        # Disable analytics and crash reporting
        settings.update({'sync': False})

        # Model
        self.model = YOLO(self.weights)
        self.tracker = Sort(max_age=30, min_hits=3, iou_threshold=0.3)

        # DB
        self.DB = kwargs.get('db_client', None)

        # Set polygon
        self.polygon = Polygon(self.counting_area)

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
            print(trans('Reconnect {location}...', location=self.location))
            if self.socketio is not None:
                self.notification(trans('Lost connection to camera!'), 'danger')

            try:
                self.vsm.reconnect()
            except Exception as e:
                # print(e)
                if self.video_stream is str:
                    print(trans('Error reconnect: {video_path}', video_path=self.video_stream))
                else:
                    print(trans('Error reconnect'))

            time.sleep(5)

    """
    Process the frame.

    Parameters:
        frame (numpy.ndarray): The frame to process.

    Returns:
        numpy.ndarray: The processed frame.
    """

    def process_frame(self, frame):
        start_time = time.time()

        frame_copy = frame.copy()
        last_total_count = self.total_count

        boxes = self.detect(frame)
        frame = self.draw_counting_area(frame)
        frame = self.detect_count(frame, boxes)
        self.frame_lost = 0

        # Save images from training dataset
        if bool(self.dataset['enable']) is True:
            if last_total_count != self.total_count and frame_copy is not None and random.random() < float(
                    self.dataset['probability']):
                if not os.path.exists(self.dataset['path']):
                    os.makedirs(self.dataset['path'])
                location_clean = re.sub('[^A-Za-z0-9-_]+', '', self.location)
                create_time = int(time.time())
                cv2.imwrite(f'{self.dataset["path"]}/{location_clean}_{create_time}.jpg',
                            frame_copy, [cv2.IMWRITE_JPEG_QUALITY, 100])

        # FPS counter on the frame
        end_time = time.time()
        fps = 1 / np.round(end_time - start_time, 2)
        cv2.putText(frame, f'FPS: {int(fps)}', (20, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 2)

        return frame

    """
    Run the generation of frames.

    Parameters:
        None

    Returns:
        None
    """

    def run_frames(self):
        while self.running:
            try:
                frame = self.vsm.get_frame()
                if frame is None:
                    self.reconnect()
                    continue

                self.frame = self.process_frame(frame)
            except Exception as e:
                print(e)
                self.reconnect()

    """
    Generator that yields frames in the form of JPEG images.

    Parameters:
        None

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
                    # Attempt to restart in case of error/missing frame
                    frame = self.vsm.get_frame()
                    if frame is None:
                        self.reconnect()
                        continue
                    frame = self.process_frame(frame)

                scale_percent = int(self.video_scale)  # percent of original size
                width = int(frame.shape[1] * scale_percent / 100)
                height = int(frame.shape[0] * scale_percent / 100)
                frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)

                ret, frame = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, int(self.video_quality)])

                frame = frame.tobytes()

                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            except Exception as e:
                print(e)

    """
    Counts the number of runs in the video stream.

    Parameters:
        None

    Returns:
        None
    """

    def count_run(self):
        while self.running:
            try:
                frame = self.vsm.get_frame()
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
        classes_list = None
        if self.classes is not None and isinstance(self.classes, dict) and len(self.classes) > 0:
            classes_list = list(map(int, self.classes.keys()))

        results = self.model.predict(
            image,
            conf=self.confidence,
            iou=self.iou,
            device=self.device,
            vid_stride=self.vid_stride,
            classes=classes_list
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
        pts = np.array(self.counting_area, np.int32)
        pts = pts.reshape((-1, 1, 2))
        cv2.fillPoly(overlay, [pts], self.counting_area_color)

        return cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0)

    """
    Draws boxes on an image and returns the modified image.

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

            # Check if the object is within the counting area
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
    
    Parameters:
        location (str): The location of the object.
        name (str): The name of the object.
        correct_count (int): The correct count.
        defect_count (int): The defect count.
        active (int): The active status.

    Returns:
        dict: The total count.
    """

    def save_count(self, location, name, correct_count, defect_count, active=1):
        total_count = int(self.total_count)
        defect_count = int(defect_count)
        correct_count = int(correct_count)
        item_count = str(total_count - defect_count + correct_count)
        if not self.DB.check_connection():
            self.notification(trans('Impossible to save! There is no connection to the database.'), 'warning')
            return dict(total=total_count, defect=defect_count, correct=correct_count)

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
            self.notification(trans('Saved successfully!'), 'success')
        else:
            self.notification(trans('Save error!'), 'danger')

        return dict(total=total_count, defect=defect_count, correct=correct_count)

    """
    Resets the count of total objects and total count.

    Parameters:
        location (str): The location of the object.

    Returns:
        None
    """

    def reset_count(self, location):
        self.total_objects = []
        self.total_count = 0
        self.current_count = 0

        if self.DB.check_connection():
            self.DB.close_current_count(location)

        self.notification(trans('Counting completed successfully!'), 'primary')

    """
    Reset the current count.

    Parameters:
        location (str): The location of the object.
        name (str): The name of the object.
        correct_count (int): The correct count.
        defect_count (int): The defect count.

    Returns:
        None
    """

    def reset_count_current(self, location, name, correct_count, defect_count):
        current_count = int(self.current_count)
        total_count = int(self.total_count)
        defect_count = int(defect_count)
        correct_count = int(correct_count)
        try:
            if self.DB.check_connection():
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
            self.notification(trans('The counter has been reset!'), 'primary')

    """
    Emit a notification to the client.

    Parameters:
        message (str): The message to be displayed.
        notification_type (str): The type of notification (success, danger, warning, info, primary, secondary).

    Returns:
        None
    """

    def notification(self, message='', notification_type='primary'):
        if self.socketio is not None:
            self.socketio.emit(f'{self.location}_notification', {'type': notification_type, 'message': message})

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
            self.notification(trans('Counting has started!'), 'success')
        self.paused = False

    """
    Stop counting.

    Parameters:
        None

    Returns:
        None
    """

    def stop(self):
        if self.socketio is not None and self.running is True:
            self.notification(trans('Counting has stopped!'), 'primary')
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
            self.notification(trans('Counting has paused!'), 'warning')
        self.paused = True

    """
    Check if the counting is paused.

    Parameters:
        None

    Returns:
        None
    """

    def is_pause(self):
        return self.paused
