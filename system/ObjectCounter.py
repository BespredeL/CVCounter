# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 01.11.2023
# Updated: 24.11.2024
# Website: https://bespredel.name

import json
import os
import random
import re
import time
from typing import Generator

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
    FPS_POSITION: tuple = (20, 70)
    FPS_FONT_SCALE: float = 1.5
    FPS_COLOR: tuple = (0, 0, 255)
    FPS_THICKNESS: int = 2
    POLYGON_ALPHA: float = 0.4

    def __init__(self, location: str, config_manager: any, socketio: any, **kwargs: dict) -> None:
        # Init variables
        self.total_objects: set = set()
        self.total_count: int = 0
        self.current_count: int = 0
        self.defect_count: int = 0
        self.correct_count: int = 0
        self.frame: np.ndarray = None
        self.frame_lost: int = 0
        self.get_frames_running: bool = False
        self.running: bool = True
        self.paused = False

        # Load and initialize config
        self._initialize_config(location, config_manager, kwargs)

        # Init logger
        self.logger: Logger = Logger()

        # Init notification manager
        self.notif_manager: NotificationManager = NotificationManager(socketio=socketio, location=location)

        # Initialize video stream manager
        self.vsm: VideoStreamManager = VideoStreamManager(self.video_path, self.video_fps)
        self.vsm.start()

        # Disable analytics and crash reporting
        settings.update({'sync': False})

        # Model
        self.model: YOLO = YOLO(self.weights)
        self.tracker: Sort = Sort(max_age=30, min_hits=3, iou_threshold=0.3)

        # Init Database manager
        self.db_manager: any = kwargs.get('db_manager', None)

        # Set polygon
        self.polygon: Polygon = Polygon(self.counting_area)

    def _initialize_config(self, location: str, config_manager: any, kwargs: dict) -> None:
        """
        Initializes the configuration for the object counter.

        Args:
            location (str): The location of the object counter.
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
            - self.video_fps (int): The frame rate of the video.
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

        config_manager.read_config()
        detector_config = config_manager.get(f"detections.{location}")

        self.debug: bool = kwargs.get('debug', config_manager.get('debug', False))
        self.location: str = location
        self.weights: str = kwargs.get('weights', detector_config.get('weights_path'))
        self.device: str = kwargs.get('device', detector_config.get('device', 'cpu'))
        self.confidence: float = kwargs.get('confidence',
                                            detector_config.get('confidence',
                                                                config_manager.get('detection_default.confidence',
                                                                                   0.5)))
        self.iou: float = kwargs.get('iou',
                                     detector_config.get('iou', config_manager.get('detection_default.iou', 0.7)))
        self.counting_area: list = kwargs.get('counting_area', detector_config.get('counting_area'))
        self.counting_area_color: tuple = kwargs.get('counting_area_color', detector_config.get('counting_area_color'))
        self.video_fps: int = detector_config.get('video_fps', config_manager.get("detection_default.video_fps"))
        self.video_scale: int = detector_config.get('video_show_scale',
                                                    config_manager.get("detection_default.video_show_scale", 50))
        self.video_quality: int = detector_config.get('video_show_quality',
                                                      config_manager.get("detection_default.video_show_quality", 50))
        self.indicator_size: int = detector_config.get('indicator_size',
                                                       config_manager.get("detection_default.indicator_size", 10))
        self.vid_stride: int = detector_config.get('vid_stride', config_manager.get("detection_default.vid_stride", 1))
        self.classes: dict = detector_config.get('classes', {})
        self.dataset: dict = detector_config.get('dataset_create', {})

        # Video
        self.video_path: str = kwargs.get('video_path', detector_config['video_path'])

        # Started counter value from config
        start_count: int = int(detector_config.get('start_total_count', 0))
        if start_count > 0:
            self.total_count: int = start_count
            self.total_objects: set = set(range(-start_count, 0))
            config_manager.set(f"detections.{self.location}.start_total_count", 0)
            config_manager.save_config()

    def _detect(self, image: np.ndarray) -> np.ndarray:
        """
        Detects objects in an image using a pre-trained model.

        Args:
            image (ndarray): The input image as a numpy array.

        Returns:
            ndarray: An array of updated results after tracking the detected objects.
        """
        classes_list = list(map(int, self.classes.keys())) if self.classes else None

        results = self.model.predict(
            image,
            conf=self.confidence,
            iou=self.iou,
            device=self.device,
            vid_stride=self.vid_stride,
            classes=classes_list,
            # stream_buffer=True,
        )

        xyxy = results[0].boxes.xyxy.cpu().numpy()
        conf = results[0].boxes.conf.cpu().numpy()
        detections = np.concatenate((xyxy, conf.reshape(-1, 1)), axis=1)
        return self.tracker.update(detections)

    def _draw_counting_area(self, image: np.ndarray) -> np.ndarray:
        """
        Draws a counting area on the given image.

        Args:
            image (numpy.ndarray): The image on which the counting area should be drawn.

        Returns:
            numpy.ndarray: The image with the counting area drawn on it.
        """
        overlay = image.copy()

        # Polygon corner points coordinates
        pts = np.array(self.counting_area, np.int32).reshape((-1, 1, 2))
        cv2.fillPoly(overlay, [pts], self.counting_area_color)

        return cv2.addWeighted(overlay, self.POLYGON_ALPHA, image, 1 - self.POLYGON_ALPHA, 0)

    def _detect_count(self, image: np.ndarray, boxes: list) -> np.ndarray:
        """
        Draws boxes on an image and returns the modified image.

        Args:
            image (numpy.ndarray): The image on which the boxes will be drawn.
            boxes (List[Tuple[int]]): A list of boxes, where each box is represented by a tuple of (x1, y1, x2, y2, rid),
                                      where x1, y1 are the top-left coordinates, x2, y2 are the bottom-right coordinates,
                                      and rid is the ID of the box.

        Returns:
            numpy.ndarray: The modified image with the boxes drawn on it.
        """
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

    def _process_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Process the frame.

        Args:
            frame (numpy.ndarray): The frame to process.

        Returns:
            numpy.ndarray: The processed frame.
        """
        start_time = time.time()
        frame_copy = frame.copy() if self.dataset.get('enable') else None
        last_total_count = self.total_count

        # Detect objects
        boxes = self._detect(frame)

        # Draw counting area
        if self.get_frames_running:
            frame = self._draw_counting_area(frame)

        # Detect counting
        frame = self._detect_count(frame, boxes)

        # Reset the frame_lost counter
        self.frame_lost = 0

        # Save images from training dataset
        if self.dataset.get('enable') and last_total_count != self.total_count and random.random() < float(
                self.dataset['probability']):
            self._save_dataset_image(frame_copy)

        # FPS counter on the frame
        if self.debug:
            fps = int(1 / (time.time() - start_time))
            cv2.putText(frame, f'FPS: {fps}',
                        self.FPS_POSITION, cv2.FONT_HERSHEY_SIMPLEX, self.FPS_FONT_SCALE, self.FPS_COLOR,
                        self.FPS_THICKNESS)

        return frame

    def _save_dataset_image(self, frame: np.ndarray) -> None:
        """
        Saves an image to the dataset path if it exists.

        Args:
            frame (numpy.ndarray): The image frame to be saved.

        Returns:
            None
        """
        if frame is None:
            return

        dataset_path = self.dataset.get('path')
        if not os.path.exists(dataset_path):
            os.makedirs(dataset_path)
        location_clean = re.sub('[^A-Za-z0-9-_]+', '', self.location)
        create_time = int(time.time())
        cv2.imwrite(f'{dataset_path}/{location_clean}_{create_time}.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 100])

    def run_frames(self) -> None:
        """
        Run the generation of frames.

        Returns:
            None
        """
        self.notif_manager.event('counter_status', {'status': 'started', 'location': self.location})

        while self.running:
            try:
                frame = self.vsm.get_frame()
                if frame is None:
                    self.frame_lost += 1
                    self.notif_manager.notify(trans('Lost connection to camera!'), 'danger')
                    time.sleep(0.01)
                    continue  # Skip the iteration if the frame is not received

                if self.frame_lost > 0:
                    self.frame_lost = 0
                    self.notif_manager.notify(trans('Connection to camera restored!'), 'success')

                if self.get_frames_running:
                    self.frame = self._process_frame(frame)
                else:
                    self.frame = None
                    self._process_frame(frame)

                time.sleep(0.01)
            except Exception as e:
                print(e)
                self.notif_manager.notify(trans('Lost connection to camera!'), 'danger')

    def get_frames(self) -> Generator:
        """
        Generator that yields frames in the form of JPEG images.

        Returns:
            A generator that yields frames in the form of JPEG images.
        """
        self.get_frames_running = True
        try:
            while self.running:
                self.get_frames_running = True

                if self.frame is not None:
                    encoded_frame = self.frame

                    # Scale the frame
                    if self.video_scale > 0:
                        encoded_frame = self.vsm.resize_frame(encoded_frame, int(self.video_scale))

                    # Encode the frame
                    encoded_frame = self.vsm.encoding_frame(encoded_frame, int(self.video_quality), 'jpeg')

                    yield b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + encoded_frame.tobytes() + b'\r\n'
                else:
                    time.sleep(0.01)  # Wait for a short pause if there is no frame yet
        except Exception as e:
            print(e)
        finally:
            self.get_frames_running = False

    def get_current_count(self) -> dict:
        """
        Get current count.

        Returns:
            dict: The current count.
        """
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

    def save_count(self, location: str, correct_count: int, defect_count: int, custom_fields: str,
                   active: int = 1) -> dict:
        """
        Save count.

        Args:
            location (str): The location of the object.
            correct_count (int): The correct count.
            defect_count (int): The defect count.
            custom_fields (str): The custom fields.
            active (int): The active status.

        Returns:
            dict: The total count.
        """
        total_count = int(self.total_count)
        defect_count = int(defect_count)
        correct_count = int(correct_count)

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

    def reset_count(self, location: str) -> None:
        """
        Resets the count of total objects and total count.

        Args:
            location (str): The location of the object.

        Returns:
            None
        """
        self.total_objects.clear()
        self.total_count = 0
        self.current_count = 0
        self.defect_count = 0
        self.correct_count = 0

        self.db_manager.close_current_count(location)

        self.notif_manager.notify(trans('Counting completed successfully!'), 'primary')

    def reset_count_current(self, location: str, correct_count: int, defect_count: int) -> None:
        """
        Reset the current count.

        Args:
            location (str): The location of the object.
            correct_count (int): The correct count.
            defect_count (int): The defect count.

        Returns:
            None
        """
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
            self.logger.error(e)

        self.current_count = 0
        self.defect_count += defect_count
        self.correct_count += correct_count

        self.notif_manager.emit(f'{location}_count', {'total': total_count, 'current': 0})
        self.notif_manager.notify(trans('The counter has been reset!'), 'primary')

    def start(self) -> None:
        """
        Start counting.

        Returns:
            None
        """
        # self.running = True
        if self.paused:
            self.notif_manager.notify(trans('Counting has started!'), 'success')
            self.notif_manager.event('counter_status', {'status': 'started', 'location': self.location})
        self.paused = False

    def stop(self) -> None:
        """
        Stop counting.

        Returns:
            None
        """
        if self.running:
            self.notif_manager.notify(trans('Counting has stopped!'), 'primary')
            self.notif_manager.event('counter_status', {'status': 'stopped', 'location': self.location})
        self.running = False

    def pause(self) -> None:
        """
        Pause counting.

        Returns:
            None
        """
        if not self.paused:
            self.notif_manager.notify(trans('Counting has paused!'), 'warning')
            self.notif_manager.event('counter_status', {'status': 'paused', 'location': self.location})
        self.paused = True

    def is_pause(self) -> bool:
        """
        Check if the counting is paused.

        Returns:
            None
        """
        return self.paused
