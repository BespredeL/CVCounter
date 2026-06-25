# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 01.11.2023
# Updated: 23.06.2026
# Website: https://bespredel.name

import json
import os
import random
import re
import time
from typing import Generator, List, Optional, Tuple

import cv2
import numpy as np
from flask_socketio import SocketIO
from numpy import ndarray
from system.managers.config_manager import ConfigManager
from system.utils.frame_utils import FrameUtils
from system.utils.logger import Logger
from system.managers.notification_manager import NotificationManager
from system.object_detection import load_detector
from system.core.sort import Sort
from system.core.timer import Timer
from system.utils.exception_handler import StreamConnectionError
from system.utils.i18n import trans
from system.managers.video_stream_manager import VideoStreamManager
from system.managers.video_recorder_manager import VideoRecorderManager

_PLACEHOLDER_MJPEG_CHUNK: bytes | None = None


def _placeholder_mjpeg_chunk() -> bytes:
    """Minimal multipart JPEG chunk so Werkzeug commits headers before the first real frame."""
    global _PLACEHOLDER_MJPEG_CHUNK
    if _PLACEHOLDER_MJPEG_CHUNK is None:
        frame = np.zeros((2, 2, 3), dtype=np.uint8)
        encoded = FrameUtils.encoding_frame(frame, 60, 'jpeg')
        _PLACEHOLDER_MJPEG_CHUNK = (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n'
                + encoded.tobytes()
                + b'\r\n'
        )
    return _PLACEHOLDER_MJPEG_CHUNK


class ObjectCounter:
    DEFAULT_FPS_POSITION: tuple = (20, 70)
    DEFAULT_FPS_FONT_SCALE: float = 1.5
    DEFAULT_FPS_COLOR: tuple = (0, 0, 255)
    DEFAULT_FPS_THICKNESS: int = 2
    DEFAULT_POLYGON_ALPHA: float = 0.4
    DEFAULT_SLEEP_TIME: float = 0.01
    DEFAULT_CONFIDENCE: float = 0.5
    DEFAULT_IOU: float = 0.7
    DEFAULT_VIDEO_QUALITY: int = 50
    DEFAULT_VIDEO_SCALE: int = 50
    DEFAULT_MAX_AGE: int = 30
    DEFAULT_MIN_HITS: int = 3
    DEFAULT_TRACKER_IOU: float = 0.3
    DEFAULT_JPEG_QUALITY: int = 90
    DEFAULT_INDICATOR_SIZE: int = 10
    DEFAULT_VID_STRIDE: int = 1
    DEFAULT_RECORDING_PATH: str = "storage/saved_recordings"
    DEFAULT_MJPEG_FPS: float = 15.0
    DEFAULT_PAUSED_SLEEP_TIME: float = 0.1
    DEFAULT_VIDEO_RECONNECT_ATTEMPTS: int = 5

    def __init__(self, location: str, config_manager: ConfigManager, socketio: SocketIO, **kwargs: any) -> None:
        # Init variables
        self.total_objects: set = set()
        self.total_count: int = 0
        self.current_count: int = 0
        self.defect_count: int = 0
        self.correct_count: int = 0
        self.frame: Optional[np.ndarray] = None
        self._mjpeg_chunk: bytes | None = None
        self._mjpeg_viewers: int = 0
        self._last_mjpeg_encode_time: float = 0.0
        self._last_count_payload: dict | None = None
        self._cached_source_frame: np.ndarray | None = None
        self.get_frames_running: bool = False
        self.running: bool = True
        self.paused = False
        self.recording_enabled: bool = False
        self.recording_base_path: str | None = None
        self.recording_scale: int = 100
        self.recording_quality: int = 80
        self.recorder: VideoRecorderManager | None = None

        # Mask for fast point-in-polygon check (generated on first frame)
        self._counting_mask: Optional[np.ndarray] = None

        # Load and initialize config
        self.__initialize_config(location, config_manager, kwargs)

        # Init logger
        self.logger: Logger = Logger()

        # Init notification manager
        self.notif_manager: NotificationManager = NotificationManager(socketio=socketio, location=location)

        # Initialize video stream manager
        self.vsm: VideoStreamManager = VideoStreamManager(
            self.video_path,
            self.video_fps,
            max_reconnect_attempts=self.video_reconnect_attempts,
        )
        if not self.vsm.connect_with_retries():
            raise StreamConnectionError(f"Cannot open video stream: {self.video_path}")

        # Init recorder (async video writer) if enabled for this detection
        self._init_recorder()

        # Init model
        classes_list = list(map(int, self.classes.keys())) if self.classes else None
        self.model = load_detector(
            model_type=self.model_type,
            weights=self.weights,
            confidence=self.confidence,
            iou=self.iou,
            device=self.device,
            vid_stride=self.vid_stride,
            classes_list=classes_list,
            verbose=self.debug,
            model_config_path=self.model_config_path,
            input_size=self.input_size,
            backend=self.backend,
            target=self.target,
            providers=self.providers,
        )

        # Init tracker
        self.tracker: Sort = Sort(max_age=self.DEFAULT_MAX_AGE, min_hits=self.DEFAULT_MIN_HITS,
                                  iou_threshold=self.DEFAULT_TRACKER_IOU)

        # Init Database manager
        self.db_manager: any = kwargs.get('db_manager', None)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_frames(self) -> None:
        """
        Run the generation of frames.

        Returns:
            None
        """
        self.notif_manager.event('counter_status', {'status': 'started', 'location': self.location})

        while self.running:
            try:
                reconnect_count = self.vsm.get_reconnect_count()
                frame = self.vsm.get_frame()
                if frame is None:
                    if self.vsm.reconnect_limit_reached():
                        self.logger.error(
                            f"Camera connection failed after {self.video_reconnect_attempts} attempts | {self.location}"
                        )
                        self.notif_manager.notify(trans('Lost connection to camera!'), 'danger')
                        self.notif_manager.event('counter_status', {'status': 'error', 'location': self.location})
                        self.stop()
                        break

                    self.notif_manager.notify(trans('Lost connection to camera!'), 'danger')
                    self.notif_manager.event('counter_status', {'status': 'error', 'location': self.location})
                    time.sleep(self.DEFAULT_SLEEP_TIME)
                    continue  # Skip the iteration if the frame is not received

                if reconnect_count > 0:
                    self.vsm.reset_reconnect_count()
                    self.notif_manager.notify(trans('Connection to camera restored!'), 'success')
                    self.notif_manager.event('counter_status', {'status': 'started', 'location': self.location})

                self._cached_source_frame = frame

                if self.get_frames_running:
                    self.frame = self._process_frame(frame)
                else:
                    self.frame = None
                    self._process_frame(frame)

                sleep_time = self.DEFAULT_PAUSED_SLEEP_TIME if self.paused else self.DEFAULT_SLEEP_TIME
                time.sleep(sleep_time)
            except Exception as e:
                self.logger.error(f"Lost connection to camera! | {self.location}: {e}")
                self.logger.log_exception()
                self.notif_manager.notify(trans('Lost connection to camera!'), 'danger')
                self.notif_manager.event('counter_status', {'status': 'error', 'location': self.location})

    def get_frames(self) -> Generator:
        """
        Generator that yields frames in the form of JPEG images.

        JPEG encoding runs in the counter thread; this generator only forwards
        the latest chunk so the HTTP worker thread stays mostly idle.

        Always yields at least one chunk so Werkzeug calls start_response
        before the client disconnects (e.g. quick navigation away from /video).

        Returns:
            A generator that yields frames in the form of JPEG images.
        """
        self._mjpeg_viewers += 1
        self.get_frames_running = True
        sent = False
        last_chunk: bytes | None = None
        try:
            while self.running or not sent:
                chunk = self._mjpeg_chunk
                if chunk is not None:
                    if chunk is not last_chunk:
                        yield chunk
                        last_chunk = chunk
                        sent = True
                elif not sent:
                    yield _placeholder_mjpeg_chunk()
                    sent = True
                time.sleep(self.DEFAULT_SLEEP_TIME)
        except GeneratorExit:
            pass
        except Exception as e:
            self.logger.error(f'Error in get_frames: {e}')
        finally:
            self._mjpeg_viewers = max(0, self._mjpeg_viewers - 1)
            if self._mjpeg_viewers == 0:
                self.get_frames_running = False
                self._mjpeg_chunk = None

    def get_live_counts(self) -> dict:
        """
        Return in-memory counts in the same shape as the Socket.IO payload.

        Returns:
            dict: total, current, defect, correct
        """
        return {
            'total': self.total_count - self.defect_count + self.correct_count,
            'current': self.current_count,
            'defect': self.defect_count,
            'correct': self.correct_count,
        }

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
            # Uncomment to reset counters
            # self.total_objects = []
            # self.total_count = 0
            # self.current_count = 0
            # Stop the current recording video
            # if self.recording_enabled and self.recorder is not None:
            #     self.recorder.stop()

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
        self._last_count_payload = None

        self.db_manager.close_current_count(location)

        # Stop the current recording video
        if self.recording_enabled and self.recorder is not None:
            self.recorder.stop()

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
        self._last_count_payload = None

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

        # Stop the current recording video
        if self.recording_enabled and self.recorder is not None:
            self.recorder.stop()

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

    def get_source_frame(self) -> Optional[np.ndarray]:
        """
        Return a raw frame from the video source (without overlays).

        Reuses the latest frame from the counter loop to avoid a second
        read/decode from the same capture device.

        Returns:
            Optional[np.ndarray]: BGR frame or None if unavailable.
        """
        cached = self._cached_source_frame
        if cached is not None:
            return cached.copy()

        try:
            return self.vsm.get_frame()
        except Exception as e:
            self.logger.error(f'Error reading source frame: {e}')
            return None

    def update_counting_area(
            self,
            counting_area: List[Tuple[int, int]],
            counting_area_color: tuple | None = None,
    ) -> None:
        """
        Update counting polygon and invalidate the point-in-polygon mask.

        Args:
            counting_area: Polygon vertices as (x, y) in frame pixel coordinates.
            counting_area_color: Optional BGR color tuple for the overlay.
        """
        if len(counting_area) < 3:
            raise ValueError('counting_area must have at least 3 points')
        self.counting_area = [(int(p[0]), int(p[1])) for p in counting_area]
        if counting_area_color is not None:
            self.counting_area_color = tuple(int(c) for c in counting_area_color)
        self._counting_mask = None

    def save_capture(self) -> None:
        """
        Save a captured image.

        Returns:
            None
        """

        try:
            frame = self.get_source_frame()
            if frame is not None:
                self._save_dataset_image(frame)
        except Exception as e:
            self.logger.error(f'Error saving captured image: {e}')

    def cleanup(self) -> None:
        """
        Cleaning resources
        """
        self.stop()
        if hasattr(self, 'recorder') and self.recording_enabled:
            self.recorder.stop()
        if hasattr(self, 'vsm'):
            self.vsm.stop()
        if hasattr(self, 'model'):
            self.model.cleanup()
        if hasattr(self, 'db_manager'):
            self.db_manager.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def __initialize_config(self, location: str, config_manager: ConfigManager, kwargs: dict) -> None:
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
            - self.debug (bool): The debug mode flag.
            - self.config_manager (ConfigManager): The ConfigManager instance.
            - self.model_type (str): The type of object detection model.
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
            - self.recording_enabled (bool): The recording enabled flag.
            - self.recording_base_path (str): The base path for recording.
            - self.recording_scale (int): The scale of the recording video.
            - self.recording_quality (int): The quality of the recording video.
            - self.total_count (int): The total count of objects.
            - self.total_objects (set): The set of total objects.

        If the 'start_total_count' key in the detector_config is greater than 0,
        sets the total_count and total_objects attributes and updates the configuration file.
        """

        config_manager.reload_config()
        detector_config = config_manager.get(f"detections.{location}")
        detection_default = config_manager.get("detection_default", {})

        self.location: str = location
        self.debug: bool = kwargs.get('debug', config_manager.get('general.debug', False))
        self.model_type = kwargs.get('model_type', detector_config.get('model_type', 'yolo'))
        self.weights: str = config_manager.resolve_path(kwargs.get('weights', detector_config.get('weights_path')))
        self.device: str = kwargs.get('device', detector_config.get('device', 'cpu'))
        self.confidence: float = kwargs.get('confidence', detector_config.get('confidence',
                                                                              detection_default.get('confidence',
                                                                                                    self.DEFAULT_CONFIDENCE)))
        self.iou: float = kwargs.get('iou', detector_config.get('iou', detection_default.get('iou', self.DEFAULT_IOU)))
        self.counting_area: List[Tuple[int, int]] = kwargs.get('counting_area', detector_config.get('counting_area'))
        self.counting_area_color: tuple = kwargs.get('counting_area_color', detector_config.get('counting_area_color'))
        self.video_fps: int = detector_config.get('video_fps', detection_default.get("video_fps"))
        self.video_reconnect_attempts: int = int(detector_config.get('video_reconnect_attempts',
                                                                     detection_default.get('video_reconnect_attempts',
                                                                                           self.DEFAULT_VIDEO_RECONNECT_ATTEMPTS), ))
        self.video_scale: int = detector_config.get('video_show_scale',
                                                    detection_default.get("video_show_scale", self.DEFAULT_VIDEO_SCALE))
        self.video_quality: int = detector_config.get('video_show_quality', detection_default.get("video_show_quality",
                                                                                                  self.DEFAULT_VIDEO_QUALITY))
        self.indicator_size: int = detector_config.get('indicator_size', detection_default.get("indicator_size",
                                                                                               self.DEFAULT_INDICATOR_SIZE))
        self.vid_stride: int = detector_config.get('vid_stride',
                                                   detection_default.get("vid_stride", self.DEFAULT_VID_STRIDE))
        self.classes: dict = detector_config.get('classes', {})
        dataset_config = dict(detector_config.get('dataset_create', {}))
        if dataset_config.get('path'):
            dataset_config['path'] = config_manager.resolve_path(dataset_config['path'])
        self.dataset: dict = dataset_config
        model_config_path = detector_config.get('model_config_path') or detection_default.get('model_config_path')
        self.model_config_path: str | None = config_manager.resolve_path(model_config_path)
        self.input_size: int | list = detector_config.get('input_size', detection_default.get('input_size', 640))
        self.backend: str | None = detector_config.get('backend', detection_default.get('backend'))
        self.target: str | None = detector_config.get('target', detection_default.get('target'))
        self.providers: list | None = detector_config.get('providers', detection_default.get('providers'))

        # Video
        self.video_path: str = kwargs.get('video_path', detector_config['video_path'])

        # Recording
        recording_default = detection_default.get('recording', {})
        recording_config = detector_config.get('recording', {})
        self.recording_enabled: bool = bool(recording_config.get('enable', recording_default.get('enable', False)))
        self.recording_base_path = config_manager.resolve_path(
            recording_config.get('path', recording_default.get('path', self.DEFAULT_RECORDING_PATH)))
        self.recording_scale: int = int(recording_config.get('scale', recording_default.get('scale', 100)))
        self.recording_quality: int = int(recording_config.get('quality', recording_default.get('quality', 80)))

        # Started counter value from config
        start_count: int = int(detector_config.get('start_total_count', 0))
        if start_count > 0:
            self.total_count: int = start_count
            self.total_objects: set = set(range(-start_count, 0))
            config_manager.set(f"detections.{self.location}.start_total_count", 0)
            config_manager.save_config()

    def _init_recorder(self) -> None:
        """
        Initializing the asynchronous recorder for current recognition.
        """
        if not self.recording_enabled:
            return

        try:
            self.recorder = VideoRecorderManager(
                location=self.location,
                base_path=self.recording_base_path,
                fps=self.video_fps,
                scale=self.recording_scale,
                quality=self.recording_quality,
            )
        except Exception as e:
            # If it was not possible to initialize the record, log it and continue the operation of the counter without recording
            self.logger.error(f"Error initializing VideoRecorderManager: {e}")
            self.recording_enabled = False

    def _start_recording_if_needed(self) -> None:
        """
        Start recording if it is enabled and not yet started.
        This method is safe to call multiple times.
        """
        if not self.recording_enabled or self.recorder is None:
            return
        try:
            self.recorder.start()
        except Exception as e:
            self.logger.error(f"Error starting VideoRecorderManager: {e}")
            self.recording_enabled = False

    def _detect(self, image: np.ndarray) -> np.ndarray:
        """
        Detects objects in an image using a pre-trained model.

        Args:
            image (ndarray): The input image as a numpy array.

        Returns:
            ndarray: An array of updated results after tracking the detected objects.
                     Each row has the following structure:
                     [x1, y1, x2, y2, track_id, (optional) class_id]
        """
        xyxy, conf, cls = self.model.detect(image=image)

        # Prepare detections for the tracker: [x1, y1, x2, y2, conf, class]
        detections = np.concatenate((xyxy, conf.reshape(-1, 1), cls.reshape(-1, 1)), axis=1)

        # Update tracker and get tracked boxes: [x1, y1, x2, y2, conf]
        tracked_boxes = self.tracker.update(detections[:, :5])

        # Attach class IDs to tracked boxes if sizes match
        if len(tracked_boxes) > 0 and len(cls) == len(tracked_boxes):
            tracked_boxes = np.concatenate((tracked_boxes, cls.reshape(-1, 1)), axis=1)

        return tracked_boxes

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

        return cv2.addWeighted(overlay, self.DEFAULT_POLYGON_ALPHA, image, 1 - self.DEFAULT_POLYGON_ALPHA, 0)

    def _draw_indicator(self, image: np.ndarray, center: tuple[int, int], rid: int) -> None:
        """
        Draws an indicator on the given image (in place).

        Args:
            image (numpy.ndarray): The image on which the indicator should be drawn.
            center (tuple[int, int]): The center coordinates of the indicator.
            rid (int): The ID of the indicator.
        """
        color = (0, 255, 0) if rid in self.total_objects else (255, 0, 255)
        cv2.circle(image, center, self.indicator_size, color, cv2.FILLED)

    def _ensure_counting_mask(self, frame_shape: Tuple[int, int]) -> None:
        """
        Lazily builds a boolean mask of the counting area for fast point checks.

        Args:
            frame_shape (Tuple[int, int]): The shape of the frame.

        Returns:
            None
        """
        if self._counting_mask is not None:
            return

        height, width = frame_shape[:2]
        mask: np.ndarray = np.zeros((height, width), dtype=np.uint8)
        pts: np.ndarray = np.asarray(self.counting_area, dtype=np.int32).reshape((-1, 1, 2))
        cv2.fillPoly(mask, [pts], 1)
        self._counting_mask = mask.astype(bool)

    def _detect_count(self, image: np.ndarray, boxes: list | np.ndarray) -> np.ndarray:
        """
        Counts objects in the given image and draws indicators on the image.

        Args:
            image (numpy.ndarray): The image on which the boxes will be drawn.
            boxes (List[Tuple[int]] | numpy.ndarray): A list of boxes, where each box is represented by a tuple of (x1, y1, x2, y2, rid),
                                      where x1, y1 are the top-left coordinates, x2, y2 are the bottom-right coordinates,
                                      and rid is the ID of the box.

        Returns:
            numpy.ndarray: The modified image with the boxes drawn on it.
        """
        if self.paused:
            return image

        # Ensure mask for fast point-in-polygon
        if boxes is not None and len(boxes) > 0:
            h, w = image.shape[:2]
            self._ensure_counting_mask((h, w))

        for result in boxes:
            x1, y1, x2, y2, rid = map(int, result[:5])
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

            # Draw indicator on the image
            self._draw_indicator(image, (cx, cy), rid)

            # Check if the object is within the counting area using mask
            if (
                    self._counting_mask is not None
                    and 0 <= cy < self._counting_mask.shape[0]
                    and 0 <= cx < self._counting_mask.shape[1]
                    and self._counting_mask[cy, cx]
                    and rid not in self.total_objects
            ):
                self.total_objects.add(rid)
                self.current_count += 1
                # Start recording as soon as the first object is detected
                self._start_recording_if_needed()

            self.total_count = len(self.total_objects)

        payload = {
            'total': self.total_count - self.defect_count + self.correct_count,
            'current': self.current_count,
            'defect': self.defect_count,
            'correct': self.correct_count,
        }
        if payload != self._last_count_payload:
            self.notif_manager.emit(f'{self.location}_count', payload)
            self._last_count_payload = payload

        return image

    def _work_frame(self, frame: np.ndarray) -> np.ndarray:
        """One owned contiguous frame per iteration (safe for async recorder/encode)."""
        return np.ascontiguousarray(frame).copy()

    def _mjpeg_encode_interval(self) -> float:
        """Minimum seconds between MJPEG encodes for the browser stream."""
        if self.video_fps and self.video_fps > 0:
            return 1.0 / float(self.video_fps)
        return 1.0 / self.DEFAULT_MJPEG_FPS

    def _maybe_encode_mjpeg(self, frame: np.ndarray) -> None:
        """Encode MJPEG only when the stream interval has elapsed."""
        now = time.monotonic()
        if now - self._last_mjpeg_encode_time < self._mjpeg_encode_interval():
            return

        chunk = self._encode_mjpeg_chunk(frame)
        if chunk is not None:
            self._mjpeg_chunk = chunk
            self._last_mjpeg_encode_time = now

    def _process_frame(self, frame: np.ndarray) -> ndarray | None:
        """
        Process the frame.

        Args:
            frame (numpy.ndarray): The frame to process.

        Returns:
            numpy.ndarray: The processed frame.
        """
        if frame is None:
            return None

        with Timer() as timer:
            if self.paused:
                display_frame = self._work_frame(frame)
                if self.get_frames_running:
                    display_frame = self._draw_counting_area(display_frame)
                    self._maybe_encode_mjpeg(display_frame)
                return display_frame

            dataset_enabled = self.dataset.get('enable', False)
            last_total_count = self.total_count

            work_frame = self._work_frame(frame)
            boxes = self._detect(work_frame)

            if self.get_frames_running:
                area_source = work_frame.copy() if dataset_enabled else work_frame
                display_frame = self._draw_counting_area(area_source)
            else:
                display_frame = work_frame.copy() if dataset_enabled else work_frame

            display_frame = self._detect_count(display_frame, boxes)

            if dataset_enabled and last_total_count != self.total_count:
                if random.random() < float(self.dataset['probability']):
                    self._save_dataset_image(work_frame, boxes, self.dataset.get('classes', None))

            if self.debug and timer.elapsed > 0:
                fps = int(round(1 / timer.elapsed))
                cv2.putText(display_frame, f'FPS: {fps}',
                            self.DEFAULT_FPS_POSITION, cv2.FONT_HERSHEY_SIMPLEX,
                            self.DEFAULT_FPS_FONT_SCALE, self.DEFAULT_FPS_COLOR, self.DEFAULT_FPS_THICKNESS)

            # Sending a frame to an asynchronous recorder
            if self.recording_enabled and self.recorder is not None:
                self.recorder.push_frame(display_frame)

            if self.get_frames_running:
                self._maybe_encode_mjpeg(display_frame)

            return display_frame

    def _encode_mjpeg_chunk(self, frame: np.ndarray) -> bytes | None:
        """
        Build one multipart JPEG chunk for the browser MJPEG stream.

        Args:
            frame (numpy.ndarray): BGR frame to encode.

        Returns:
            bytes | None: Encoded multipart chunk or None on failure.
        """
        if frame is None:
            return None

        try:
            stream_frame = frame
            if self.video_scale > 0:
                stream_frame = FrameUtils.resize_frame(stream_frame, int(self.video_scale))

            encoded_frame = FrameUtils.encoding_frame(stream_frame, int(self.video_quality), 'jpeg')
            return (
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n'
                    + encoded_frame.tobytes()
                    + b'\r\n'
            )
        except Exception as e:
            self.logger.error(f'Error encoding MJPEG chunk: {e}')
            return None

    def _save_dataset_image(self, frame: np.ndarray, boxes: list | np.ndarray = None,
                            classes_to_save: dict = None) -> None:
        """
        Saves a raw image frame to the dataset path (without overlays or detection marks).

        Args:
            frame (numpy.ndarray): Original BGR frame to be saved.
            boxes: Detected objects used only for optional class filtering.
            classes_to_save: Optional class filter from dataset config.
        """
        if frame is None:
            return

        try:
            dataset_path = self.dataset.get('path')
            if not dataset_path:
                self.logger.warning('Dataset path is not configured')
                return

            if classes_to_save and boxes is not None and len(boxes) > 0:
                detected_classes = [int(result[-1]) for result in boxes]
                if not any(str(cls) in classes_to_save for cls in detected_classes):
                    return

            os.makedirs(dataset_path, exist_ok=True)

            location_clean = re.sub('[^A-Za-z0-9-_]+', '', self.location)
            create_time = int(time.time())

            image_path = f'{dataset_path}/{location_clean}_{create_time}.jpg'
            success = cv2.imwrite(
                image_path,
                np.ascontiguousarray(frame),
                [cv2.IMWRITE_JPEG_QUALITY, self.DEFAULT_JPEG_QUALITY],
            )

            if not success:
                self.logger.error(f'Failed to save image to {image_path}')

        except Exception as e:
            self.logger.error(f'Error saving dataset image: {e}')
