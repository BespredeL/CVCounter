# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from collections import deque
import json
import os
from pathlib import Path
import random
import re
import threading
import time
from typing import Any, Generator, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from flask_socketio import SocketIO
from numpy import ndarray
from system.managers.config_manager import ConfigManager
from system.utils.frame_utils import FrameUtils
from system.utils.logger import Logger
from system.managers.notification_manager import NotificationManager
from system.object_detection import load_detector
from system.core.byte_tracker import BYTETracker
from system.core.timer import Timer
from system.utils.counting_area import (
    DEFAULT_COUNTING_AREA_COLOR,
    DIRECTION_VECTORS,
    areas_to_runtime,
    normalize_counting_areas,
)
from system.utils.validators import normalize_color_value
from system.utils.exception_handler import StreamConnectionError
from system.utils.i18n import trans
from system.managers.video_stream_manager import VideoStreamManager
from system.managers.video_recorder_manager import VideoRecorderManager
from system.utils.telemetry import get_telemetry

_PLACEHOLDER_MJPEG_CHUNK: bytes | None = None
_LABEL_FONT: ImageFont.ImageFont | None = None
_LABEL_FONT_SIZE: int = 13


def _get_label_font(size: int = 13) -> ImageFont.ImageFont | None:
    """
    Get a cached TrueType font that supports Unicode / Cyrillic, falling back to default.
    """
    global _LABEL_FONT, _LABEL_FONT_SIZE
    if _LABEL_FONT is not None and _LABEL_FONT_SIZE == size:
        return _LABEL_FONT

    font_candidates = [
        "arial.ttf",
        "segoeui.ttf",
        "tahoma.ttf",
        "calibri.ttf",
        "DejaVuSans.ttf",
        "LiberationSans-Regular.ttf",
        "FreeSans.ttf",
    ]
    for font_name in font_candidates:
        try:
            _LABEL_FONT = ImageFont.truetype(font_name, size)
            _LABEL_FONT_SIZE = size
            return _LABEL_FONT
        except Exception:
            continue

    try:
        _LABEL_FONT = ImageFont.load_default()
        _LABEL_FONT_SIZE = size
    except Exception:
        _LABEL_FONT = None
    return _LABEL_FONT


_BADGE_CACHE: dict[tuple[str, tuple[int, int, int]], np.ndarray] = {}
_MAX_BADGE_CACHE_SIZE: int = 500


def _render_cached_badge(label: str, color: tuple[int, int, int], font: ImageFont.ImageFont) -> np.ndarray:
    """
    Renders or fetches a cached text badge image for bounding box indicators.
    """
    global _BADGE_CACHE
    key = (label, color)
    cached = _BADGE_CACHE.get(key)
    if cached is not None:
        return cached

    mask_w, mask_h = font.getmask(label).size
    pad_x, pad_y = 5, 3
    badge_w = mask_w + pad_x * 2
    badge_h = mask_h + pad_y * 2 + 2

    # BGR to RGB for PIL
    rgb_color = (int(color[2]), int(color[1]), int(color[0]))
    img = Image.new('RGB', (badge_w, badge_h), color=rgb_color)
    draw = ImageDraw.Draw(img)
    draw.text((pad_x, pad_y), label, font=font, fill=(0, 0, 0))
    badge_np = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)

    if len(_BADGE_CACHE) >= _MAX_BADGE_CACHE_SIZE:
        _BADGE_CACHE.clear()
    _BADGE_CACHE[key] = badge_np
    return badge_np



def _placeholder_mjpeg_chunk() -> bytes:
    """
    Minimal multipart JPEG chunk so Werkzeug commits headers before the first real frame.
    
    Args:
        None

    Returns:
        bytes: The placeholder JPEG chunk
    """
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
    DEFAULT_MAX_AGE: int = 60
    DEFAULT_MIN_HITS: int = 3
    DEFAULT_TRACKER_IOU: float = 0.3
    DEFAULT_JPEG_QUALITY: int = 90
    DEFAULT_INDICATOR_SIZE: int = 10
    DEFAULT_INDICATOR_MODE: str = 'circle'
    DEFAULT_INDICATOR_DETECTED_COLOR: Tuple[int, int, int] = (255, 0, 255)
    DEFAULT_INDICATOR_COUNTED_COLOR: Tuple[int, int, int] = (0, 255, 0)
    DEFAULT_VID_STRIDE: int = 1
    DEFAULT_RECORDING_PATH: str = "storage/saved_recordings"
    DEFAULT_MJPEG_FPS: float = 25.0
    DEFAULT_PAUSED_SLEEP_TIME: float = 0.1
    DEFAULT_VIDEO_RECONNECT_ATTEMPTS: int = 5

    def __init__(self, location: str, config_manager: ConfigManager, socketio: SocketIO, **kwargs: any) -> None:
        """
        Initialize the ObjectCounter.
        
        Args:
            location (str): The location of the object.
            config_manager (ConfigManager): The config manager.
            socketio (SocketIO): The socketio instance.
            **kwargs: Arbitrary keyword arguments

        Returns:
            None
        """

        # Init variables
        self.total_objects: set = set()
        self._total_objects_queue: deque = deque()
        self._max_tracked_history: int = 30000
        self._track_history: dict[int, deque] = {}
        self._max_track_history_len: int = 15
        self.total_count: int = 0
        self.current_count: int = 0
        self.defect_count: int = 0
        self.correct_count: int = 0
        self.pending_defect_count: int = 0
        self.pending_correct_count: int = 0
        self.class_counts: dict[int, int] = {}
        self.current_class_counts: dict[int, int] = {}
        self.frame: Optional[np.ndarray] = None
        self._mjpeg_chunk: bytes | None = None
        self._mjpeg_viewers: int = 0
        self._last_mjpeg_encode_time: float = 0.0
        self._playout_thread: threading.Thread | None = None
        self._playout_stop = False
        self._playout_active = False
        self._playout_boxes: list = []
        self._last_det_seq = -1
        self._last_count_payload: dict | None = None
        self._cached_source_frame: np.ndarray | None = None
        self.get_frames_running: bool = False
        self.running: bool = True
        self.paused = False
        self.recording_enabled: bool = False
        self.recording_base_path: str | None = None
        self.recording_scale: int = 100
        self.recording_quality: int = 80
        self.recording_idle_timeout: float = 0.0
        self._last_recording_activity: float = 0.0
        self.recorder: VideoRecorderManager | None = None

        # Mask for fast point-in-polygon check (generated on first frame)
        self._counting_mask: Optional[np.ndarray] = None

        # Stream performance diagnostics
        self._perf_frame_count: int = 0
        self._perf_total_frame_time: float = 0.0
        self._perf_total_inference_time: float = 0.0
        self._perf_last_report_time: float = time.monotonic()
        self._perf_report_interval: float = 300.0
        self._hud_cam_fps = 0.0
        self._hud_out_fps = 0.0
        self._hud_inf_ms = 0.0
        self._out_count = 0
        self._out_tick = time.monotonic()

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

        # Model and preview / data collection mode state
        self.preview_mode: bool = False
        self.interval_capture_active: bool = False
        self.interval_capture_interval: float = 3.0
        self.interval_capture_max: int = 50
        self.interval_capture_count: int = 0
        self.interval_capture_dataset: str | None = None
        self.interval_capture_split: str = 'inbox'
        self._last_interval_capture_time: float = 0.0

        weights_exist = bool(self.weights and os.path.isfile(self.weights))
        model_type_str = str(getattr(self, 'model_type', 'auto') or 'auto').lower()
        if not weights_exist or model_type_str in ('none', 'preview'):
            self.model = None
            self.preview_mode = True
            self.logger.info(
                f"Location '{self.location}' running in Data Collection / Preview mode (weights: {self.weights or 'none'})."
            )
        else:
            try:
                active_classes = []
                for cls_id, cls_entry in (self.classes or {}).items():
                    try:
                        cid = int(cls_id)
                    except (ValueError, TypeError):
                        continue
                    if isinstance(cls_entry, dict):
                        if cls_entry.get('enabled', True):
                            active_classes.append(cid)
                    else:
                        active_classes.append(cid)
                classes_list = active_classes if (self.classes and active_classes) else None
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
            except Exception as e:
                self.logger.warning(
                    f"Could not load detector for '{self.location}': {e}. Falling back to Data Collection mode."
                )
                self.model = None
                self.preview_mode = True

        # Init tracker (ByteTrack)
        self.tracker: BYTETracker = BYTETracker(
            track_thresh=max(0.2, self.confidence * 0.7),
            iou_threshold=self.DEFAULT_TRACKER_IOU,
            max_age=self.DEFAULT_MAX_AGE,
            min_hits=self.DEFAULT_MIN_HITS,
        )

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
        status_evt = 'collection' if self.preview_mode else 'started'
        self.notif_manager.event('counter_status', {'status': status_evt, 'location': self.location})

        while self.running:
            try:
                if self._playout_active:
                    shown_seq = self.vsm.shown_seq()
                    if shown_seq == self._last_det_seq:
                        time.sleep(0.004)
                        continue

                reconnect_count = self.vsm.get_reconnect_count()
                frame = self.vsm.get_frame()
                if frame is None:
                    if self.vsm.reconnect_limit_reached():
                        self.logger.error(
                            f"Camera connection failed after {self.video_reconnect_attempts} attempts | {self.location}"
                        )
                        get_telemetry().track('stream_lost', {'location': self.location, 'reason': 'reconnect_limit'})
                        self.notif_manager.notify(trans('Lost connection to camera!'), 'danger')
                        self.notif_manager.event('counter_status', {'status': 'error', 'location': self.location})
                        self.stop()
                        break

                    get_telemetry().track('stream_lost', {'location': self.location, 'reason': 'frame_none'})
                    self.notif_manager.notify(trans('Lost connection to camera!'), 'danger')
                    self.notif_manager.event('counter_status', {'status': 'error', 'location': self.location})
                    time.sleep(self.DEFAULT_SLEEP_TIME)
                    continue  # Skip the iteration if the frame is not received

                if reconnect_count > 0:
                    self.vsm.reset_reconnect_count()
                    get_telemetry().track('stream_reconnected', {'location': self.location})
                    self.notif_manager.notify(trans('Connection to camera restored!'), 'success')
                    self.notif_manager.event('counter_status', {'status': 'started', 'location': self.location})

                self._cached_source_frame = frame
                if self._playout_active:
                    self._last_det_seq = self.vsm.shown_seq()

                if self.get_frames_running:
                    self.frame = self._process_frame(frame)
                else:
                    self.frame = None
                    self._process_frame(frame)

                sleep_time = self.DEFAULT_PAUSED_SLEEP_TIME if self.paused else self.DEFAULT_SLEEP_TIME
                time.sleep(sleep_time)
            except Exception as e:
                self.logger.error(f"Error processing frame | {self.location}: {e}")
                self.logger.log_exception()
                get_telemetry().track('stream_lost', {'location': self.location, 'reason': 'exception', 'error': str(e)})
                self.notif_manager.notify(trans(f"Counter processing error: {e}"), 'danger')
                self.notif_manager.event('counter_status', {'status': 'error', 'location': self.location})
                time.sleep(self.DEFAULT_PAUSED_SLEEP_TIME)

    def get_frames(self) -> Generator:
        """
        Generator that yields frames in the form of JPEG images.

        JPEG for an RTSP queue is encoded on a playout thread. This generator only
        forwards the latest chunk so the HTTP worker stays mostly idle.

        Always yields at least one chunk so Werkzeug calls start_response
        before the client disconnects (e.g. quick navigation away from /video).

        Returns:
            A generator that yields frames in the form of JPEG images.
        """
        self._mjpeg_viewers += 1
        self.get_frames_running = True
        if self.vsm.uses_live_queue():
            self._start_playout()
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
                self._stop_playout()

    def _class_label(self, class_id: int) -> str:
        """
        Resolve a human-readable label for a detection class id.
        
        Args:
            class_id (int): The class id.

        Returns:
            str: The human-readable label
        """
        if class_id < 0:
            return trans('Unknown')

        if self.classes:
            label = self.classes.get(str(class_id), self.classes.get(class_id))
            if label:
                if isinstance(label, dict):
                    name = label.get('name')
                    return str(name) if (name is not None and str(name).strip()) else str(class_id)
                return str(label)

        return trans('Class {id}', id=class_id)

    def _configured_class_ids(self) -> set[int]:
        """
        Class ids declared in detection config (may be empty).
        
        Args:
            None

        Returns:
            set[int]: The set of class ids
        """
        ids: set[int] = set()
        if not self.classes:
            return ids

        for key, val in self.classes.items():
            try:
                cid = int(key)
            except (TypeError, ValueError):
                continue
            if isinstance(val, dict):
                if val.get('enabled', True):
                    ids.add(cid)
            else:
                ids.add(cid)
        return ids

    def _by_class_payload(self) -> list[dict]:
        """
        Build sorted per-class breakdown for live UI / Socket.IO.
        
        Args:
            None

        Returns:
            list[dict]: The list of class payloads
        """
        class_ids = (
                set(self.class_counts.keys())
                | set(self.current_class_counts.keys())
                | self._configured_class_ids()
        )
        return [
            {
                'id': class_id,
                'name': self._class_label(class_id),
                'total': int(self.class_counts.get(class_id, 0)),
                'current': int(self.current_class_counts.get(class_id, 0)),
            }
            for class_id in sorted(class_ids)
        ]

    def _increment_class_count(self, class_id: int) -> None:
        """
        Increment total and current-batch counts for a class.
        
        Args:
            class_id (int): The class id.

        Returns:
            None
        """
        key = int(class_id)
        self.class_counts[key] = self.class_counts.get(key, 0) + 1
        self.current_class_counts[key] = self.current_class_counts.get(key, 0) + 1

    def get_live_counts(self) -> dict:
        """
        Return in-memory counts in the same shape as the Socket.IO payload.

        Returns:
            dict: total, current, defect, correct, pending_defect, pending_correct, by_class
        """
        return {
            'total': self.total_count - self.defect_count + self.correct_count,
            'current': self.current_count,
            'defect': self.defect_count,
            'correct': self.correct_count,
            'pending_defect': self.pending_defect_count,
            'pending_correct': self.pending_correct_count,
            'by_class': self._by_class_payload(),
        }

    def emit_live_counts(self, force: bool = False) -> None:
        """
        Broadcast current counts to all connected clients.

        Args:
            force (bool): Emit even when the payload is unchanged.
        """
        payload = self.get_live_counts()
        if force or payload != self._last_count_payload:
            self.notif_manager.emit(f'{self.location}_count', payload)
            self._last_count_payload = payload

    def set_pending_counts(self, pending_defect: int, pending_correct: int) -> dict:
        """
        Update unsaved defect / correct keyboard values and broadcast them.

        Args:
            pending_defect (int): Pending defect count.
            pending_correct (int): Pending correct count adjustment.

        Returns:
            dict: Current live counts payload.
        """
        self.pending_defect_count = max(int(pending_defect), 0)
        self.pending_correct_count = int(pending_correct)
        self.emit_live_counts(force=True)
        return self.get_live_counts()

    def clear_pending_counts(self) -> None:
        """
        Reset pending keyboard values to zero.
        
        Returns:
            None
        """
        self.pending_defect_count = 0
        self.pending_correct_count = 0

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
            'class_counts': json.loads(result.class_counts) if result.class_counts else [],
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
        defect_count = int(defect_count if defect_count is not None and defect_count != 0 else self.pending_defect_count)
        correct_count = int(correct_count if correct_count is not None and correct_count != 0 else self.pending_correct_count)

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
            active=active,
            class_counts=self._by_class_payload(),
        )

        if result:
            self.notif_manager.notify(trans('Saved successfully!'), 'success')
        else:
            self.notif_manager.notify(trans('Save error!'), 'danger')

        self.clear_pending_counts()
        self.emit_live_counts(force=True)

        return dict(total=total_count, defect=defect_count, correct=correct_count)

    def reset_count(self, location: str) -> None:
        """
        Resets the count of total objects and total count.

        Args:
            location (str): The location of the object.

        Returns:
            None
        """

        final_class_counts = self._by_class_payload()

        self.total_objects.clear()
        self._total_objects_queue.clear()
        self._track_history.clear()
        self.total_count = 0
        self.current_count = 0
        self.defect_count = 0
        self.correct_count = 0
        self.class_counts.clear()
        self.current_class_counts.clear()
        self.clear_pending_counts()
        self._last_count_payload = None

        # Reset active tracker state so old tracks don't instantly re-trigger
        self.tracker = BYTETracker(
            track_thresh=max(0.2, self.confidence * 0.7),
            iou_threshold=self.DEFAULT_TRACKER_IOU,
            max_age=self.DEFAULT_MAX_AGE,
            min_hits=self.DEFAULT_MIN_HITS,
        )

        self.db_manager.close_current_count(location, class_counts=final_class_counts)

        # Stop the current recording video
        self._stop_recording()

        self.notif_manager.notify(trans('Counting completed successfully!'), 'primary')
        self.emit_live_counts(force=True)

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
        defect_count = int(defect_count if defect_count is not None and defect_count != 0 else self.pending_defect_count)
        correct_count = int(correct_count if correct_count is not None and correct_count != 0 else self.pending_correct_count)
        by_class = self._by_class_payload()
        try:
            self.db_manager.save_part_result(
                location=location,
                current_count=current_count,
                total_count=total_count,
                defects_count=defect_count,
                correct_count=correct_count,
                by_class=by_class,
                class_counts=by_class,
            )
        except Exception as e:
            print(e)
            self.logger.error(e)

        self.current_count = 0
        self.current_class_counts.clear()
        self.defect_count += defect_count
        self.correct_count += correct_count
        self.clear_pending_counts()
        self.emit_live_counts(force=True)

        self.notif_manager.notify(trans('The counter has been reset!'), 'primary')

    def start(self) -> None:
        """
        Start counting.

        Args:
            None

        Returns:
            None
        """
        # self.running = True
        if self.paused:
            self.notif_manager.notify(trans('Counting has started!'), 'success')
            status_evt = 'collection' if self.preview_mode else 'started'
            self.notif_manager.event('counter_status', {'status': status_evt, 'location': self.location})
        self.paused = False

    def stop(self) -> None:
        """
        Stop counting.

        Args:
            None

        Returns:
            None
        """
        if self.running:
            self._maybe_report_performance(force=True)
            self.notif_manager.notify(trans('Counting has stopped!'), 'primary')
            self.notif_manager.event('counter_status', {'status': 'stopped', 'location': self.location})
        self.running = False

        # Stop the current recording video
        self._stop_recording()

    def pause(self) -> None:
        """
        Pause counting.

        Args:
            None

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

        Args:
            None

        Returns:
            bool: True if the counting is paused, False otherwise
        """
        return self.paused

    def get_source_frame(self) -> Optional[np.ndarray]:
        """
        Return a raw frame from the video source (without overlays).

        Reuses the latest frame from the counter loop to avoid a second
        read/decode from the same capture device.

        Args:
            None

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

    def update_counting_areas(self, counting_areas: list | None) -> None:
        """
        Replace all counting zones and invalidate the point-in-polygon mask.

        Args:
            counting_areas: List of zones ``{'points': [...], 'color': [...]}``.

        Returns:
            None
        """
        normalized = normalize_counting_areas({'counting_areas': counting_areas or []})
        runtime = areas_to_runtime(normalized)
        if not runtime:
            raise ValueError('counting_areas must contain at least one zone with 3+ points')

        self.counting_areas = runtime
        self.counting_area = list(runtime[0]['points'])
        self.counting_area_color = tuple(runtime[0]['color'])
        self.counting_area_direction = str(runtime[0].get('direction', 'any'))
        self._counting_mask = None

    def update_counting_area(
            self,
            counting_area: List[Tuple[int, int]] | None = None,
            counting_area_color: tuple | None = None,
            counting_areas: list | None = None,
    ) -> None:
        """
        Update counting polygon(s) and invalidate the point-in-polygon mask.

        Args:
            counting_area: Legacy single polygon vertices as (x, y).
            counting_area_color: Optional BGR color tuple for the first/legacy zone.
            counting_areas: Preferred multi-zone payload.

        Returns:
            None
        """
        if counting_areas is not None:
            self.update_counting_areas(counting_areas)
            return

        if counting_area is None or len(counting_area) < 3:
            raise ValueError('counting_area must have at least 3 points')

        color = (
            tuple(int(c) for c in counting_area_color)
            if counting_area_color is not None
            else tuple(self.counting_area_color or DEFAULT_COUNTING_AREA_COLOR)
        )
        self.update_counting_areas([{
            'points': [(int(p[0]), int(p[1])) for p in counting_area],
            'color': list(color),
        }])

    def save_capture(self, target_dataset: Optional[str] = None, split: str = 'inbox') -> Optional[str]:
        """
        Save a captured image directly or to a dataset.

        Args:
            target_dataset: Optional dataset name.
            split: Dataset split ('inbox', 'train', 'val').

        Returns:
            Optional[str]: Saved file path or None on failure.
        """
        try:
            frame = self.get_source_frame()
            if frame is not None:
                return self._save_dataset_image(frame, target_dataset=target_dataset, split=split)
        except Exception as e:
            self.logger.error(f'Error saving captured image: {e}')
        return None

    def start_interval_capture(
            self,
            interval_sec: float = 2.0,
            max_frames: int = 30,
            target_dataset: Optional[str] = None,
            split: str = 'inbox',
    ) -> dict:
        """
        Start periodic background frame capturing.
        """
        self.interval_capture_interval = max(0.2, float(interval_sec))
        self.interval_capture_max = max(1, int(max_frames))
        self.interval_capture_dataset = target_dataset
        self.interval_capture_split = split
        self.interval_capture_count = 0
        self._last_interval_capture_time = time.monotonic()
        self.interval_capture_active = True
        return self.get_interval_capture_status()

    def stop_interval_capture(self) -> dict:
        """
        Stop periodic background frame capturing.
        """
        self.interval_capture_active = False
        return self.get_interval_capture_status()

    def get_interval_capture_status(self) -> dict:
        """
        Get status of periodic background frame capturing.
        """
        return {
            'active': bool(self.interval_capture_active),
            'count': int(self.interval_capture_count),
            'max_frames': int(self.interval_capture_max),
            'interval': float(self.interval_capture_interval),
            'dataset': self.interval_capture_dataset,
            'split': self.interval_capture_split,
        }

    def cleanup(self) -> None:
        """
        Cleaning resources

        Args:
            None

        Returns:
            None
        """
        self.stop()
        self._stop_recording()
        if hasattr(self, 'vsm') and self.vsm is not None:
            self.vsm.stop()
        if hasattr(self, 'model') and self.model is not None:
            self.model.cleanup()
        if hasattr(self, 'db_manager') and self.db_manager is not None:
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
            - self.counting_areas (list): Counting zones with points and colors.
            - self.counting_area (list): Legacy alias of the first zone points.
            - self.counting_area_color (tuple): Legacy alias of the first zone color.
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
            - self.recording_idle_timeout (float): Seconds without detections before stopping recording (0 = until reset).
            - self.total_count (int): The total count of objects.
            - self.total_objects (set): The set of total objects.

        If the 'start_total_count' key in the detector_config is greater than 0,
        sets the total_count and total_objects attributes and updates the configuration file.
        """

        config_manager.reload_config()
        detector_config = config_manager.get(f"detections.{location}") or {}
        detection_default = config_manager.get("detection_default", {}) or {}

        self.config_manager: ConfigManager = config_manager
        self.location: str = location
        self.debug: bool = kwargs.get('debug', config_manager.get('general.debug', False))
        self.show_fps: bool = bool(config_manager.get('general.show_fps', False))
        self.model_type: str = str(kwargs.get(
            'model_type',
            detector_config.get('model_type', detection_default.get('model_type', 'auto'))
        ) or 'auto')
        raw_weights = kwargs.get('weights', detector_config.get('weights_path'))
        self.weights: str = config_manager.resolve_path(raw_weights) if raw_weights else ""
        self.device: str = kwargs.get('device', detector_config.get('device', 'cpu'))
        self.confidence: float = kwargs.get('confidence', detector_config.get('confidence',
                                                                              detection_default.get('confidence',
                                                                                                    self.DEFAULT_CONFIDENCE)))
        self.iou: float = kwargs.get('iou', detector_config.get('iou', detection_default.get('iou', self.DEFAULT_IOU)))
        counting_areas = normalize_counting_areas(
            detector_config,
            counting_areas=kwargs.get('counting_areas'),
            counting_area=kwargs.get('counting_area'),
            counting_area_color=kwargs.get('counting_area_color'),
        )
        runtime_areas = areas_to_runtime(counting_areas)
        if not runtime_areas:
            runtime_areas = [{
                'points': [(0, 0), (100, 0), (100, 100), (0, 100)],
                'color': tuple(DEFAULT_COUNTING_AREA_COLOR),
            }]
        self.counting_areas: list[dict] = runtime_areas
        self.counting_area: List[Tuple[int, int]] = list(runtime_areas[0]['points'])
        self.counting_area_color: tuple = tuple(runtime_areas[0]['color'])
        self.counting_area_direction: str = str(runtime_areas[0].get('direction', 'any'))
        self.video_fps: int = detector_config.get('video_fps', detection_default.get("video_fps", 0)) or 0
        self.video_reconnect_attempts: int = int(detector_config.get('video_reconnect_attempts',
                                                                     detection_default.get('video_reconnect_attempts',
                                                                                           self.DEFAULT_VIDEO_RECONNECT_ATTEMPTS), ))
        self.video_scale: int = detector_config.get('video_show_scale',
                                                    detection_default.get("video_show_scale", self.DEFAULT_VIDEO_SCALE))
        self.video_quality: int = detector_config.get('video_show_quality', detection_default.get("video_show_quality",
                                                                                                  self.DEFAULT_VIDEO_QUALITY))
        self.indicator_size: int = detector_config.get('indicator_size', detection_default.get("indicator_size",
                                                                                               self.DEFAULT_INDICATOR_SIZE))
        self.indicator_mode: str = str(
            detector_config.get(
                'indicator_mode',
                detection_default.get("indicator_mode", self.DEFAULT_INDICATOR_MODE)
            )
        ).strip().lower()
        if self.indicator_mode not in ('circle', 'box'):
            self.indicator_mode = self.DEFAULT_INDICATOR_MODE

        raw_det_color = detector_config.get(
            'indicator_detected_color',
            detection_default.get('indicator_detected_color', self.DEFAULT_INDICATOR_DETECTED_COLOR)
        )
        try:
            self.indicator_detected_color: tuple[int, int, int] = tuple(
                normalize_color_value(raw_det_color, 'indicator_detected_color')
            )
        except Exception:
            self.indicator_detected_color = self.DEFAULT_INDICATOR_DETECTED_COLOR

        raw_cnt_color = detector_config.get(
            'indicator_counted_color',
            detection_default.get('indicator_counted_color', self.DEFAULT_INDICATOR_COUNTED_COLOR)
        )
        try:
            self.indicator_counted_color: tuple[int, int, int] = tuple(
                normalize_color_value(raw_cnt_color, 'indicator_counted_color')
            )
        except Exception:
            self.indicator_counted_color = self.DEFAULT_INDICATOR_COUNTED_COLOR

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
        self.video_path: str = kwargs.get('video_path', detector_config.get('video_path', ''))

        # Recording
        recording_default = detection_default.get('recording', {})
        recording_config = detector_config.get('recording', {})
        self.recording_enabled: bool = bool(recording_config.get('enable', recording_default.get('enable', False)))
        self.recording_base_path = config_manager.resolve_path(
            recording_config.get('path', recording_default.get('path', self.DEFAULT_RECORDING_PATH)))
        self.recording_scale: int = int(recording_config.get('scale', recording_default.get('scale', 100)))
        self.recording_quality: int = int(recording_config.get('quality', recording_default.get('quality', 80)))
        self.recording_idle_timeout: float = float(
            recording_config.get('idle_timeout', recording_default.get('idle_timeout', 0))
        )
        if self.recording_idle_timeout < 0:
            self.recording_idle_timeout = 0.0

        # Started counter value from config
        start_count: int = int(detector_config.get('start_total_count', 0))
        if start_count > 0:
            self.total_count = start_count
            start_ids = range(-start_count, 0)
            self.total_objects = set(start_ids)
            self._total_objects_queue = deque(start_ids, maxlen=self._max_tracked_history)
            config_manager.set(f"detections.{self.location}.start_total_count", 0)
            config_manager.save_config()

        # Periodic interval frame capture attributes
        self.interval_capture_active: bool = False
        self.interval_capture_interval: float = 2.0
        self.interval_capture_max: int = 30
        self.interval_capture_dataset: Optional[str] = None
        self.interval_capture_split: str = 'inbox'
        self.interval_capture_count: int = 0
        self._last_interval_capture_time: float = 0.0

    def _init_recorder(self) -> None:
        """
        Initializing the asynchronous recorder for current recognition.

        Args:
            None

        Returns:
            None
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

        Args:
            None

        Returns:
            None
        """
        if not self.recording_enabled or self.recorder is None:
            return
        try:
            self.recorder.start()
        except Exception as e:
            self.logger.error(f"Error starting VideoRecorderManager: {e}")
            self.recording_enabled = False

    def _stop_recording(self) -> None:
        """
        Stop the current recording session and clear idle activity tracking.

        Args:
            None

        Returns:
            None
        """
        self._last_recording_activity = 0.0
        if self.recorder is None:
            return
        try:
            self.recorder.stop()
        except Exception as e:
            self.logger.error(f"Error stopping VideoRecorderManager: {e}")

    def _on_detection_activity(self) -> None:
        """
        Mark detection activity and start recording when objects are present in the frame.

        Args:
            None

        Returns:
            None
        """
        if not self.recording_enabled or self.recorder is None:
            return
        self._last_recording_activity = time.monotonic()
        self._start_recording_if_needed()

    def _stop_recording_if_idle(self) -> None:
        """
        Stop recording when no objects were detected for recording_idle_timeout seconds.
        When idle_timeout is 0 or less, recording continues until reset/stop.

        Args:
            None

        Returns:
            None
        """
        if (
                not self.recording_enabled
                or self.recorder is None
                or self.recording_idle_timeout <= 0
                or not self.recorder.is_recording()
                or self._last_recording_activity <= 0
        ):
            return

        if time.monotonic() - self._last_recording_activity >= self.recording_idle_timeout:
            self._stop_recording()

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
        if self.model is None or self.preview_mode:
            return self.tracker.update(np.empty((0, 6)))

        xyxy, conf, cls = self.model.detect(image=image)

        if xyxy is None or len(xyxy) == 0:
            return self.tracker.update(np.empty((0, 6)))

        # Prepare detections for the tracker: [x1, y1, x2, y2, conf, class]
        n_dets = len(xyxy)
        detections = np.empty((n_dets, 6), dtype=np.float32)
        detections[:, :4] = xyxy
        detections[:, 4] = conf
        detections[:, 5] = cls

        # Tracked boxes: [x1, y1, x2, y2, track_id, class_id]
        return self.tracker.update(detections)

    def _draw_counting_area(self, image: np.ndarray) -> np.ndarray:
        """
        Draws all counting zones on the given image.

        Args:
            image (numpy.ndarray): The image on which the counting area should be drawn.

        Returns:
            numpy.ndarray: The image with the counting area drawn on it.
        """
        overlay = image.copy()
        zones = self.counting_areas or [{
            'points': self.counting_area,
            'color': self.counting_area_color,
        }]

        for zone in zones:
            points = zone.get('points') or []
            if len(points) < 3:
                continue
            pts = np.array(points, np.int32).reshape((-1, 1, 2))
            color = tuple(zone.get('color') or self.counting_area_color or DEFAULT_COUNTING_AREA_COLOR)
            cv2.fillPoly(overlay, [pts], color)

            # Draw directional arrow on zone if configured
            direction = zone.get('direction', 'any')
            if direction != 'any':
                M = cv2.moments(pts)
                if M['m00'] != 0:
                    mcx = int(M['m10'] / M['m00'])
                    mcy = int(M['m01'] / M['m00'])
                else:
                    mcx = int(np.mean(pts[:, 0, 0]))
                    mcy = int(np.mean(pts[:, 0, 1]))

                arrow_len = 35
                vec = DIRECTION_VECTORS.get(direction)
                if vec:
                    ux, uy = vec
                    p1 = (int(mcx - arrow_len * ux), int(mcy - arrow_len * uy))
                    p2 = (int(mcx + arrow_len * ux), int(mcy + arrow_len * uy))
                    cv2.arrowedLine(overlay, p1, p2, (0, 0, 0), 4, tipLength=0.35, line_type=cv2.LINE_AA)
                    cv2.arrowedLine(overlay, p1, p2, (255, 255, 255), 2, tipLength=0.35, line_type=cv2.LINE_AA)

        return cv2.addWeighted(overlay, self.DEFAULT_POLYGON_ALPHA, image, 1 - self.DEFAULT_POLYGON_ALPHA, 0)

    def set_indicator_mode(self, mode: str) -> str:
        """
        Set the indicator display mode ('circle' or 'box').

        Args:
            mode (str): The indicator mode.

        Returns:
            str: Active indicator mode.
        """
        mode = str(mode).strip().lower()
        if mode not in ('circle', 'box'):
            mode = self.DEFAULT_INDICATOR_MODE
        self.indicator_mode = mode
        return self.indicator_mode

    def set_indicator_colors(
        self,
        detected_color: Any = None,
        counted_color: Any = None,
    ) -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
        """
        Dynamically update indicator state colors.

        Args:
            detected_color: Color for detected uncounted objects (hex str or BGR sequence).
            counted_color: Color for counted objects (hex str or BGR sequence).

        Returns:
            Tuple[Tuple[int, int, int], Tuple[int, int, int]]: Active (detected_color, counted_color).
        """
        if detected_color is not None:
            try:
                self.indicator_detected_color = tuple(normalize_color_value(detected_color, 'indicator_detected_color'))
            except Exception as e:
                self.logger.warning(f"Failed to set indicator_detected_color: {e}")
        if counted_color is not None:
            try:
                self.indicator_counted_color = tuple(normalize_color_value(counted_color, 'indicator_counted_color'))
            except Exception as e:
                self.logger.warning(f"Failed to set indicator_counted_color: {e}")
        return self.indicator_detected_color, self.indicator_counted_color

    def _draw_indicator(
        self,
        image: np.ndarray,
        center: tuple[int, int],
        rid: int,
        box: tuple[int, int, int, int] | None = None,
        class_id: int = -1,
    ) -> None:
        """
        Draws an indicator on the given image (in place).

        Args:
            image (numpy.ndarray): The image on which the indicator should be drawn.
            center (tuple[int, int]): The center coordinates of the indicator.
            rid (int): The ID of the indicator.
            box (tuple[int, int, int, int], optional): (x1, y1, x2, y2) bounding box.
            class_id (int, optional): The class ID of the object.

        Returns:
            None
        """
        color = self.indicator_counted_color if rid in self.total_objects else self.indicator_detected_color

        if self.indicator_mode == 'box' and box is not None:
            x1, y1, x2, y2 = box
            # Draw bounding box rectangle
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)

            # Center tracking dot (subtle, so users see the point triggering the counting zone)
            dot_radius = max(3, min(self.indicator_size // 2, 6))
            cv2.circle(image, center, dot_radius, color, cv2.FILLED)

            # Prepare text badge: Class name + track ID
            cls_name = self._class_label(class_id)
            label = f"{cls_name} #{rid}" if rid is not None and rid >= 0 else cls_name

            font = _get_label_font(13)
            img_h, img_w = image.shape[:2]

            if font is not None:
                badge = _render_cached_badge(label, color, font)
                badge_h, badge_w = badge.shape[:2]

                badge_x1 = max(0, min(x1, img_w - badge_w))
                badge_x2 = min(img_w, badge_x1 + badge_w)

                if y1 - badge_h >= 0:
                    badge_y1 = y1 - badge_h
                    badge_y2 = y1
                else:
                    badge_y1 = min(img_h - 1, max(0, y1))
                    badge_y2 = min(img_h, badge_y1 + badge_h)

                bw = badge_x2 - badge_x1
                bh = badge_y2 - badge_y1

                if bw > 0 and bh > 0:
                    image[badge_y1:badge_y2, badge_x1:badge_x2] = badge[:bh, :bw]
            else:
                (text_w, text_h), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                badge_h = text_h + baseline + 4
                badge_y1 = max(0, y1 - badge_h) if y1 - badge_h >= 0 else min(img_h - badge_h, y1)
                badge_y2 = badge_y1 + badge_h
                badge_x2 = min(img_w, x1 + text_w + 6)
                cv2.rectangle(image, (x1, badge_y1), (badge_x2, badge_y2), color, cv2.FILLED)
                cv2.putText(image, label, (x1 + 3, badge_y2 - baseline - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
        else:
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
        mask: np.ndarray = np.zeros((height, width), dtype=np.int16)
        zones = self.counting_areas or [{
            'points': self.counting_area,
            'color': self.counting_area_color,
            'direction': getattr(self, 'counting_area_direction', 'any'),
        }]

        for idx, zone in enumerate(zones):
            points = zone.get('points') or []
            if len(points) < 3:
                continue
            pts = np.asarray(points, dtype=np.int32).reshape((-1, 1, 2))
            cv2.fillPoly(mask, [pts], idx + 1)

        self._counting_mask = mask

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
            values = list(map(int, result[:6]))
            x1, y1, x2, y2, rid = values[:5]
            class_id = values[5] if len(values) > 5 else -1
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

            # Track trajectory history for motion direction validation
            if rid not in self._track_history:
                self._track_history[rid] = deque(maxlen=self._max_track_history_len)
            self._track_history[rid].append((cx, cy))

            # Draw indicator on the image
            self._draw_indicator(image, (cx, cy), rid, box=(x1, y1, x2, y2), class_id=class_id)

            # Check if the object is within the counting area using mask
            if (
                    self._counting_mask is not None
                    and 0 <= cy < self._counting_mask.shape[0]
                    and 0 <= cx < self._counting_mask.shape[1]
                    and rid not in self.total_objects
            ):
                zone_code = int(self._counting_mask[cy, cx])
                if zone_code > 0:
                    zone_idx = zone_code - 1
                    zone = self.counting_areas[zone_idx] if zone_idx < len(self.counting_areas) else None
                    direction = zone.get('direction', 'any') if zone else 'any'

                    is_valid_direction = True
                    if direction != 'any':
                        vec = DIRECTION_VECTORS.get(direction)
                        if vec:
                            hist = self._track_history[rid]
                            if len(hist) >= 2:
                                start_x, start_y = hist[0]
                                dx = cx - start_x
                                dy = cy - start_y
                                dist = (dx * dx + dy * dy) ** 0.5
                                min_delta = 5.0  # minimum displacement pixels to ignore stationary jitter

                                if dist >= min_delta:
                                    ux, uy = vec
                                    # Cosine of angle between motion vector and target direction
                                    dot = (dx * ux + dy * uy) / dist
                                    # dot >= 0.5 corresponds to +-60 degree acceptance cone
                                    is_valid_direction = (dot >= 0.5)
                                else:
                                    is_valid_direction = False
                            else:
                                is_valid_direction = False

                    if is_valid_direction:
                        self.total_objects.add(rid)
                        self._total_objects_queue.append(rid)
                        self.total_count += 1
                        self.current_count += 1
                        self._increment_class_count(class_id)
                        if len(self._total_objects_queue) > self._max_tracked_history:
                            old_id = self._total_objects_queue.popleft()
                            self.total_objects.discard(old_id)

        if len(self._track_history) > 1000:
            active_rids = {int(b[4]) for b in boxes} if boxes is not None and len(boxes) > 0 else set()
            self._track_history = {
                k: v for k, v in self._track_history.items()
                if k in active_rids or k in self.total_objects
            }

        self.emit_live_counts()

        return image

    def _work_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        One owned contiguous frame per iteration (safe for async recorder/encode).
        
        Args:
            frame (numpy.ndarray): The frame to process.

        Returns:
            numpy.ndarray: The processed frame.
        """
        return np.ascontiguousarray(frame).copy()

    def _mjpeg_encode_interval(self) -> float:
        """
        Minimum seconds between MJPEG encodes for the browser stream.
        
        Args:
            None

        Returns:
            float: The minimum seconds between MJPEG encodes
        """
        if self.video_fps and self.video_fps > 0:
            return 1.0 / float(self.video_fps)
        return 1.0 / self.DEFAULT_MJPEG_FPS

    def _snapshot_boxes(self, boxes) -> list:
        if boxes is None:
            return []
        snapped = []
        for result in boxes:
            try:
                snapped.append(tuple(int(v) for v in list(result)[:6]))
            except Exception:
                continue
        return snapped

    def _start_playout(self) -> None:
        thread = self._playout_thread
        if thread is not None and thread.is_alive():
            self._playout_stop = False
            self._playout_active = True
            self.vsm.set_follow_shown(True)
            return
        self._playout_stop = False
        self._playout_active = True
        self.vsm.set_follow_shown(True)
        self._playout_thread = threading.Thread(target=self._playout_loop, name="mjpeg-playout", daemon=True)
        self._playout_thread.start()

    def _stop_playout(self) -> None:
        self._playout_stop = True
        self._playout_active = False
        self.vsm.set_follow_shown(False)
        self._last_det_seq = -1

    def _playout_loop(self) -> None:
        """Send queued RTSP frames at capture speed. Detection reads the newest frame and does not drain this queue."""
        while not self._playout_stop:
            frame = self.vsm.pop_live_frame()
            if frame is None:
                time.sleep(0.004)
                continue
            try:
                display = self._draw_counting_area(frame)
                for values in self._playout_boxes:
                    x1, y1, x2, y2, rid = values[:5]
                    class_id = values[5] if len(values) > 5 else -1
                    self._draw_indicator(
                        display,
                        ((x1 + x2) // 2, (y1 + y2) // 2),
                        rid,
                        box=(x1, y1, x2, y2),
                        class_id=class_id,
                    )
                self._draw_fps_hud(display)
                chunk = self._encode_mjpeg_chunk(display)
                if chunk is not None:
                    self._note_output_frame()
                    self._mjpeg_chunk = chunk
            except Exception as exc:
                self.logger.error(f"MJPEG playout error | {self.location}: {exc}")
                time.sleep(0.02)

    def _note_output_frame(self) -> None:
        self._out_count += 1
        now = time.monotonic()
        span = now - self._out_tick
        if span >= 0.5:
            self._hud_out_fps = self._out_count / span
            self._out_count = 0
            self._out_tick = now

    def _draw_fps_hud(self, image: np.ndarray) -> None:
        """
        Draw camera FPS, output FPS, and inference time in the top-left corner.

        Shown when general.show_fps is enabled. Drawn on the frame that is encoded
        for the browser, including the RTSP playout path.
        """
        if not self.show_fps or image is None or image.size == 0:
            return
        try:
            self._hud_cam_fps = float(self.vsm.capture_fps())
        except Exception:
            pass

        height, width = image.shape[:2]
        panel_w, panel_h = 188, 84
        if width < panel_w + 24 or height < panel_h + 24:
            return
        x, y = 16, 16
        roi = image[y:y + panel_h, x:x + panel_w]
        tint = np.empty_like(roi)
        tint[:] = (28, 30, 34)
        cv2.addWeighted(tint, 0.82, roi, 0.18, 0, roi)
        cv2.rectangle(image, (x, y), (x + panel_w - 1, y + panel_h - 1), (90, 96, 104), 1, cv2.LINE_AA)

        rows = (
            ("CAM", f"{self._hud_cam_fps:4.1f}", "fps"),
            ("OUT", f"{self._hud_out_fps:4.1f}", "fps"),
            ("INF", f"{self._hud_inf_ms:4.1f}", "ms"),
        )
        font = cv2.FONT_HERSHEY_SIMPLEX
        for index, (label, value, unit) in enumerate(rows):
            baseline = y + 24 + index * 24
            cv2.putText(image, label, (x + 12, baseline), font, 0.52, (168, 174, 182), 1, cv2.LINE_AA)
            cv2.putText(image, value, (x + 68, baseline), font, 0.58, (248, 248, 248), 1, cv2.LINE_AA)
            cv2.putText(image, unit, (x + 138, baseline), font, 0.42, (148, 154, 162), 1, cv2.LINE_AA)

    def _maybe_encode_mjpeg(self, frame: np.ndarray) -> None:
        """
        Encode MJPEG only when the stream interval has elapsed.
        
        Args:
            frame (numpy.ndarray): The frame to process.

        Returns:
            None
        """
        now = time.monotonic()
        if now - self._last_mjpeg_encode_time < self._mjpeg_encode_interval():
            return

        chunk = self._encode_mjpeg_chunk(frame)
        if chunk is not None:
            self._note_output_frame()
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
                if self.get_frames_running and not self._playout_active:
                    display_frame = self._draw_counting_area(display_frame)
                    self._draw_fps_hud(display_frame)
                    self._maybe_encode_mjpeg(display_frame)
                return display_frame

            dataset_enabled = self.dataset.get('enable', False)
            last_total_count = self.total_count

            work_frame = self._work_frame(frame)
            inf_start = time.monotonic()
            boxes = self._detect(work_frame)
            inf_duration = time.monotonic() - inf_start
            inf_ms = inf_duration * 1000.0
            self._hud_inf_ms = inf_ms if self._hud_inf_ms <= 0 else (self._hud_inf_ms * 0.8 + inf_ms * 0.2)
            self._playout_boxes = self._snapshot_boxes(boxes)

            if boxes is not None and len(boxes) > 0:
                self._on_detection_activity()

            if self.get_frames_running:
                area_source = work_frame.copy() if dataset_enabled else work_frame
                display_frame = self._draw_counting_area(area_source)
            else:
                display_frame = work_frame.copy() if dataset_enabled else work_frame

            display_frame = self._detect_count(display_frame, boxes)

            if dataset_enabled and last_total_count != self.total_count:
                if random.random() < float(self.dataset.get('probability', 0.1)):
                    self._save_dataset_image(work_frame, boxes, self.dataset.get('classes', None))

            # Periodic interval capture
            if self.interval_capture_active:
                now_m = time.monotonic()
                if now_m - self._last_interval_capture_time >= self.interval_capture_interval:
                    self._last_interval_capture_time = now_m
                    saved = self._save_dataset_image(
                        work_frame,
                        target_dataset=self.interval_capture_dataset,
                        split=self.interval_capture_split,
                    )
                    if saved:
                        self.interval_capture_count += 1
                        if self.interval_capture_count >= self.interval_capture_max:
                            self.interval_capture_active = False

            if self.show_fps:
                self._draw_fps_hud(display_frame)
            elif self.debug and timer.elapsed > 0:
                fps = int(round(1 / timer.elapsed))
                cv2.putText(display_frame, f'FPS: {fps}',
                            self.DEFAULT_FPS_POSITION, cv2.FONT_HERSHEY_SIMPLEX,
                            self.DEFAULT_FPS_FONT_SCALE, self.DEFAULT_FPS_COLOR, self.DEFAULT_FPS_THICKNESS)

            # Sending a frame to an asynchronous recorder while an active session is running
            if self.recording_enabled and self.recorder is not None and self.recorder.is_recording():
                self.recorder.push_frame(display_frame)

            self._stop_recording_if_idle()

            # Record performance metrics
            self._perf_frame_count += 1
            self._perf_total_inference_time += inf_duration
            self._perf_total_frame_time += timer.elapsed
            self._maybe_report_performance()

            if self.get_frames_running and not self._playout_active:
                self._maybe_encode_mjpeg(display_frame)

            return display_frame

    def _maybe_report_performance(self, force: bool = False) -> None:
        """
        Record and report aggregate FPS and inference performance metrics.
        
        Args:
            force: Force metric dispatch regardless of interval window.
            
        Returns:
            None
        """
        now = time.monotonic()
        elapsed = now - self._perf_last_report_time
        if (elapsed >= self._perf_report_interval and self._perf_frame_count >= 20) or (force and self._perf_frame_count >= 5):
            avg_fps = self._perf_frame_count / max(0.001, elapsed)
            avg_inf_ms = (self._perf_total_inference_time / max(1, self._perf_frame_count)) * 1000.0
            avg_frame_ms = (self._perf_total_frame_time / max(1, self._perf_frame_count)) * 1000.0
            get_telemetry().track('stream_performance', {
                'location': self.location,
                'model_type': str(getattr(self, 'model_type', 'unknown')),
                'backend': str(getattr(self, 'backend', 'unknown')),
                'fps': round(avg_fps, 1),
                'inference_ms': round(avg_inf_ms, 1),
                'frame_ms': round(avg_frame_ms, 1),
                'frames_count': self._perf_frame_count,
            })
            self._perf_frame_count = 0
            self._perf_total_frame_time = 0.0
            self._perf_total_inference_time = 0.0
            self._perf_last_report_time = now

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

    def _save_dataset_image(
            self,
            frame: np.ndarray,
            boxes: list | np.ndarray = None,
            classes_to_save: dict = None,
            target_dataset: Optional[str] = None,
            split: str = 'inbox',
    ) -> Optional[str]:
        """
        Saves a raw image frame to the dataset or storage path (without overlays or detection marks).

        Args:
            frame (numpy.ndarray): Original BGR frame to be saved.
            boxes: Detected objects used only for optional class filtering.
            classes_to_save: Optional class filter from dataset config.
            target_dataset: Optional dataset name to save into storage/datasets/<name>/images/<split>.
            split: Dataset split ('inbox', 'train', 'val').

        Returns:
            Optional[str]: Saved file path or None on failure.
        """
        if frame is None:
            return None

        try:
            from system.utils.paths import get_project_root, resolve_project_path
            if target_dataset:
                root_path = Path(get_project_root())
                dataset_path = str(root_path / 'storage' / 'datasets' / target_dataset / 'images' / split)
            else:
                raw_path = self.dataset.get('path') if hasattr(self, 'dataset') and isinstance(self.dataset, dict) else None
                if not raw_path:
                    raw_path = f'storage/saved_images/{self.location}'
                if hasattr(self, 'config_manager') and self.config_manager and hasattr(self.config_manager, 'resolve_path'):
                    dataset_path = self.config_manager.resolve_path(raw_path)
                else:
                    dataset_path = str(resolve_project_path(raw_path))

            if classes_to_save and boxes is not None and len(boxes) > 0:
                detected_classes = [int(result[-1]) for result in boxes]
                if not any(str(cls) in classes_to_save for cls in detected_classes):
                    return None

            os.makedirs(dataset_path, exist_ok=True)

            location_clean = re.sub(r'[^A-Za-z0-9-_]+', '', self.location)
            create_time = int(time.time() * 1000)

            image_path = f'{dataset_path}/{location_clean}_{create_time}.jpg'
            success = cv2.imwrite(
                image_path,
                np.ascontiguousarray(frame),
                [cv2.IMWRITE_JPEG_QUALITY, self.DEFAULT_JPEG_QUALITY],
            )

            if not success:
                self.logger.error(f'Failed to save image to {image_path}')
                return None

            return image_path

        except Exception as e:
            self.logger.error(f'Error saving dataset image: {e}')
            return None
