# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 01.11.2023
# Updated: 17.10.2024
# Website: https://bespredel.name

import json
import os
import random
import re
import time

import cv2
import numpy as np
from shapely.geometry import Point, Polygon
from ultralytics import YOLO, settings

from system.Logger import Logger
from system.NotificationManager import NotificationManager
from system.VideoStreamManager import VideoStreamManager
from system.helpers import trans
from system.sort import Sort


class ObjectCounter:
    FRAME_LOST_THRESHOLD = 10
    RECONNECT_DELAY = 5  # seconds
    MAX_RECONNECT_DELAY = 60  # seconds
    FPS_POSITION = (20, 70)
    FPS_FONT_SCALE = 1.5
    FPS_COLOR = (0, 0, 255)
    FPS_THICKNESS = 2
    POLYGON_ALPHA = 0.4

    def __init__(self, location, config_manager, socketio, **kwargs):
        # Init variables
        self.total_objects = set()
        self.total_count = 0
        self.current_count = 0
        self.defect_count = 0
        self.correct_count = 0
        self.frame = None
        self.frame_lost = 0
        self.running = True
        self.paused = False

        # Load and initialize config
        self._initialize_config(location, config_manager, kwargs)

        # Init logger
        self.logger = Logger(f'error_{self.location}.log' if self.location else config_manager.get("general.log_path"))

        # Init notification manager
        self.notif_manager = NotificationManager(socketio=socketio, location=location)

        # Initialize video stream manager
        self.vsm = VideoStreamManager(self.video_path)
        self.vsm.start()

        # Disable analytics and crash reporting
        settings.update({'sync': False})

        # Model
        self.model = YOLO(self.weights)
        self.tracker = Sort(max_age=30, min_hits=3, iou_threshold=0.3)

        # Init Database manager
        self.db_manager = kwargs.get('db_manager', None)

        # Set polygon
        self.polygon = Polygon(self.counting_area)

    """
    Initializes the configuration for the object counter.

    Parameters:
        location (str): The location of the object counter.
        socketio (SocketIO): The SocketIO instance.
        config_manager (ConfigManager): The configuration object.
        kwargs (dict): Additional keyword arguments.

    Returns:
        None

    Initializes the following attributes:
        - self.location (str): The location of the object counter.
        - self.config_manager (ConfigManager): The ConfigManager instance.
        - self.weights (str): The path to the weights file.
        - self.device (str): The device to use for inference ('cpu' by default).
        - self.confidence (float): The confidence threshold for object detection.
        - self.iou (float): The IoU threshold for object detection.
        - self.counting_area (list): The coordinates of the counting area.
        - self.counting_area_color (tuple): The color of the counting area.
        - self.video_scale (int): The scale of the video.
        - self.video_quality (int): The quality of the video.
        - self.indicator_size (int): The size of the indicator.
        - self.vid_stride (int): The stride for video processing.
        - self.classes (dict): The classes for object detection.
        - self.dataset (dict): The dataset for creating the object counter.
        - self.video_path (str): The path to the video.
        - self.total_count (int): The total count of objects.
        - self.total_objects (set): The set of total objects.

    If the 'start_total_count' key in the detector_config is greater than 0, 
    sets the total_count and total_objects attributes and updates the configuration file.
    """

    def _initialize_config(self, location, config_manager, kwargs):
        config_manager.read_config()
        detector_config = config_manager.get(f"detections.{location}")

        self.location = location
        self.weights = kwargs.get('weights', detector_config.get('weights_path'))
        self.device = kwargs.get('device', detector_config.get('device', 'cpu'))
        self.confidence = kwargs.get('confidence',
                                     detector_config.get('confidence', config_manager.get('detection_default.confidence', 0.5)))
        self.iou = kwargs.get('iou', detector_config.get('iou', config_manager.get('detection_default.iou', 0.7)))
        self.counting_area = kwargs.get('counting_area', detector_config.get('counting_area'))
        self.counting_area_color = kwargs.get('counting_area_color', detector_config.get('counting_area_color'))
        self.video_scale = detector_config.get('video_show_scale', config_manager.get("detection_default.video_show_scale", 50))
        self.video_quality = detector_config.get('video_show_quality', config_manager.get("detection_default.video_show_quality", 50))
        self.indicator_size = detector_config.get('indicator_size', config_manager.get("detection_default.indicator_size", 10))
        self.vid_stride = detector_config.get('vid_stride', config_manager.get("detection_default.vid_stride", 1))
        self.classes = detector_config.get('classes', {})
        self.dataset = detector_config.get('dataset_create', {})

        # Video
        self.video_path = kwargs.get('video_path', detector_config['video_path'])

        # Started counter value from config
        start_count = int(detector_config.get('start_total_count', 0))
        if start_count > 0:
            self.total_count = start_count
            self.total_objects = set(range(-start_count, 0))
            config_manager.set(f"detections.{self.location}.start_total_count", 0)
            config_manager.save_config()

    """
    Reconnects to the video stream if the connection has been lost for more than N frames.

    Parameters:
        None

    Returns:
        None
    """

    def _reconnect(self):
        self.frame = None
        self.frame_lost += 1
        if self.frame_lost > self.FRAME_LOST_THRESHOLD:
            self.frame_lost = 0
            # self.logger.log_error('Reconnect ' + self.location + '...')
            print(trans('Reconnect {location}...', location=self.location))
            self.notif_manager.notify(trans('Lost connection to camera!'), 'danger')

            try:
                self.vsm.reconnect()
            except Exception as e:
                # print(e)
                print(trans('Error reconnect: {location}', location=self.location))

            # Sleep for N seconds before reconnecting
            print(trans('Sleeping for {delay} seconds before next reconnect attempt.', delay=self.RECONNECT_DELAY))
            time.sleep(self.RECONNECT_DELAY)

            # Increase the delay for the next attempt (exponential growth)
            self.RECONNECT_DELAY = min(self.RECONNECT_DELAY * 2, self.MAX_RECONNECT_DELAY)

    """
    Process the frame.

    Parameters:
        frame (numpy.ndarray): The frame to process.

    Returns:
        numpy.ndarray: The processed frame.
    """

    def _process_frame(self, frame):
        start_time = time.time()
        frame_copy = frame.copy()
        last_total_count = self.total_count

        boxes = self._detect(frame)
        frame = self._draw_counting_area(frame)
        frame = self._detect_count(frame, boxes)
        self.frame_lost = 0

        # Save images from training dataset
        if self.dataset.get('enable') and last_total_count != self.total_count and random.random() < float(self.dataset['probability']):
            self._save_dataset_image(frame_copy)

        # FPS counter on the frame
        fps = int(1 / (time.time() - start_time))
        cv2.putText(frame, f'FPS: {fps}',
                    self.FPS_POSITION, cv2.FONT_HERSHEY_SIMPLEX, self.FPS_FONT_SCALE, self.FPS_COLOR, self.FPS_THICKNESS)

        return frame

    """
    Saves an image to the dataset path if it exists.

    Parameters:
        frame (numpy.ndarray): The image frame to be saved.

    Returns:
        None
    """

    def _save_dataset_image(self, frame):
        dataset_path = self.dataset.get('path')
        if not os.path.exists(dataset_path):
            os.makedirs(dataset_path)
        location_clean = re.sub('[^A-Za-z0-9-_]+', '', self.location)
        create_time = int(time.time())
        cv2.imwrite(f'{dataset_path}/{location_clean}_{create_time}.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 100])

    """
    Run the generation of frames.

    Parameters:
        None

    Returns:
        None
    """

    def run_frames(self):
        self.notif_manager.event('counter_status', {'status': 'started', 'location': self.location})

        while self.running:
            try:
                frame = self.vsm.get_frame()
                if frame is None:
                    self._reconnect()
                    continue
                self.frame = self._process_frame(frame)
            except Exception as e:
                print(e)
                self._reconnect()

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
                frame = self.frame if self.frame is not None else self._reconnect_and_get_frame()
                if frame is None:
                    continue
                frame = self.vsm.resize_frame(frame, int(self.video_scale))
                frame = self.vsm.encoding_frame(frame, int(self.video_quality), 'jpg')
                yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + frame.tobytes() + b'\r\n')
            except Exception as e:
                print(e)

    """
    Retrieves a frame from the video stream manager (vsm) and processes it.

    This function first calls the `get_frame()` method of the `vsm` object to retrieve a frame. 
    If the frame is `None`, it calls the `reconnect()` method to reconnect to the video stream. 
    Finally, it calls the `process_frame()` method to process the frame and returns the processed frame.

    Returns:
        The processed frame obtained from the video stream.
    """

    def _reconnect_and_get_frame(self):
        frame = self.vsm.get_frame()
        if frame is None:
            self._reconnect()
        return self._process_frame(frame)

    """
    Counts the number of runs in the video stream.

    Parameters:
        None

    Returns:
        None
    """

    def count_run(self):
        self.notif_manager.event('counter_status', {'status': 'started', 'location': self.location})

        while self.running:
            try:
                frame = self.vsm.get_frame()
                if frame is None:
                    self._reconnect()
                    continue
                boxes = self._detect(frame)
                self._detect_count(frame, boxes)
            except Exception as e:
                print(e)
                self._reconnect()

    """
    Detects objects in an image using a pre-trained model.

    Parameters:
        image (ndarray): The input image as a numpy array.

    Returns:
        ndarray: An array of updated results after tracking the detected objects.
    """

    def _detect(self, image):
        classes_list = list(map(int, self.classes.keys())) if self.classes else None

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

    def _draw_counting_area(self, image):
        overlay = image.copy()

        # Polygon corner points coordinates
        pts = np.array(self.counting_area, np.int32).reshape((-1, 1, 2))
        cv2.fillPoly(overlay, [pts], self.counting_area_color)

        return cv2.addWeighted(overlay, self.POLYGON_ALPHA, image, 1 - self.POLYGON_ALPHA, 0)

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

    def _detect_count(self, image, boxes):
        if self.paused:
            return image

        indicator_size = int(self.indicator_size)

        for result in boxes:
            x1, y1, x2, y2, rid = map(int, result[:5])  # Unpack all values as integers
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            color = (0, 255, 0) if rid in self.total_objects else (255, 0, 255)
            cv2.circle(image, (cx, cy), indicator_size, color, cv2.FILLED)

            # Check if the object is within the counting area
            point = Point(cx, cy)
            if point.within(self.polygon) and rid not in self.total_objects:
                self.total_objects.add(rid)
                self.current_count += 1

            self.total_count = len(self.total_objects)

        self.notif_manager.emit(f'{self.location}_count', {
            'total': self.total_count - self.defect_count + self.correct_count,
            'current': self.current_count,
            'defect': self.defect_count,
            'correct': self.correct_count
        })

        return image

    """
    Get current count.

    Parameters:
        None

    Returns:
        dict: The current count.
    """

    def get_current_count(self):
        result = self.db_manager.get_current_count(self.location)
        if result is None:
            return {}

        return {
            'active': result.active,
            'location': result.location,
            'total_count': result.total_count,
            'source_count': result.source_count,
            'defects_count': result.defects_count,
            'correct_count': result.correct_count,
            'parts': json.loads(result.parts) if result.parts else [],
            'custom_fields': json.loads(result.custom_fields) if result.custom_fields else [],
            'created_at': result.created_at.strftime("%Y-%m-%d %H:%M:%S") if result.created_at else None,
            'updated_at': result.updated_at.strftime("%Y-%m-%d %H:%M:%S") if result.updated_at else None
        }

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

    def save_count(self, location, correct_count, defect_count, custom_fields, active=1):
        total_count = int(self.total_count)
        defect_count = int(defect_count)
        correct_count = int(correct_count)
        # current_total_count = str(total_count - defect_count + correct_count)

        # self.total_count = self.total_count - defect_count + correct_count
        self.defect_count += defect_count
        self.correct_count += correct_count
        self.current_count = self.current_count - defect_count + correct_count
        current_total_count = str(total_count - self.defect_count + self.correct_count)

        result = self.db_manager.save_result(
            location=location,
            total_count=current_total_count,
            source_count=total_count,
            correct_count=self.correct_count,
            defects_count=self.defect_count,
            custom_fields=custom_fields,
            active=active
        )

        if result:
            # self.total_objects = []
            # self.total_count = 0
            # self.current_count = 0
            self.notif_manager.notify(trans('Saved successfully!'), 'success')
        else:
            self.notif_manager.notify(trans('Save error!'), 'danger')

        return dict(total=total_count, defect=defect_count, correct=correct_count)

    """
    Resets the count of total objects and total count.

    Parameters:
        location (str): The location of the object.

    Returns:
        None
    """

    def reset_count(self, location):
        self.total_objects.clear()
        self.total_count = 0
        self.current_count = 0
        self.defect_count = 0
        self.correct_count = 0

        self.db_manager.close_current_count(location)

        self.notif_manager.notify(trans('Counting completed successfully!'), 'primary')

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

    def reset_count_current(self, location, correct_count, defect_count):
        current_count = int(self.current_count)
        total_count = int(self.total_count)
        defect_count = int(defect_count)
        correct_count = int(correct_count)
        try:
            self.db_manager.save_part_result(
                location=location,
                current_count=current_count,
                total_count=total_count,
                defects_count=defect_count,
                correct_count=correct_count
            )
        except Exception as e:
            print(e)

        self.current_count = 0
        self.defect_count += defect_count
        self.correct_count += correct_count

        self.notif_manager.emit(f'{location}_count', {'total': total_count, 'current': 0})
        self.notif_manager.notify(trans('The counter has been reset!'), 'primary')

    """
    Start counting.

    Parameters:
        None

    Returns:
        None
    """

    def start(self):
        # self.running = True
        if self.paused:
            self.notif_manager.notify(trans('Counting has started!'), 'success')
            self.notif_manager.event('counter_status', {'status': 'started', 'location': self.location})
        self.paused = False

    """
    Stop counting.

    Parameters:
        None

    Returns:
        None
    """

    def stop(self):
        if self.running:
            self.notif_manager.notify(trans('Counting has stopped!'), 'primary')
            self.notif_manager.event('counter_status', {'status': 'stopped', 'location': self.location})
        self.running = False

    """
    Pause counting.

    Parameters:
        None

    Returns:
        None
    """

    def pause(self):
        if not self.paused:
            self.notif_manager.notify(trans('Counting has paused!'), 'warning')
            self.notif_manager.event('counter_status', {'status': 'paused', 'location': self.location})
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
