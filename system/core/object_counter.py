# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from collections import deque
import os
import threading
from typing import Any, Generator, List, Optional, Tuple

import numpy as np
from system.managers.config_manager import ConfigManager
from system.utils.logger import Logger
from system.detection import load_detector
from system.core.byte_tracker import BYTETracker
from system.core.count_state import CountState
from system.core.counter_config import CounterSettings
from system.core.counter_loop import CounterLoop
from system.core.dataset_capture import DatasetCapture
from system.core.frame_renderer import FrameRenderer
from system.core.mjpeg_stream import MjpegBroadcaster
from system.core.perf_reporter import PerfReporter
from system.core.ports import CountingEventSink, CountStore
from system.core.recording_control import RecordingControl
from system.core.sort import Sort
from system.utils.counting_area import (
    DEFAULT_COUNTING_AREA_COLOR,
    areas_to_runtime,
    normalize_counting_areas,
)
from system.utils.validators import normalize_color_value
from system.utils.exception_handler import StreamConnectionError
from system.utils.i18n import trans
from system.managers.video_stream_manager import VideoStreamManager


class ObjectCounter:
    def __init__(self, location: str, config_manager: ConfigManager, socketio: Any,
                 event_sink: CountingEventSink | None = None,
                 store: CountStore | None = None, **kwargs: any) -> None:
        """
        Initialize the ObjectCounter.
        
        Args:
            location (str): The location of the object.
            config_manager (ConfigManager): The config manager.
            socketio (Any): The socketio instance, used only when no event sink is given.
            event_sink (CountingEventSink, optional): Outward events; defaults to Socket.IO.
            store (CountStore, optional): Count persistence; defaults to the `db_manager` kwarg.
            **kwargs: Arbitrary keyword arguments

        Returns:
            None
        """

        # Init synchronization lock
        self._lock: threading.RLock = threading.RLock()
        self._generation: int = 0

        # Init variables
        self.counts: CountState = CountState()
        self.total_objects: set = set()
        self._total_objects_queue: deque = deque()
        self._max_tracked_history: int = 30000
        self._track_history: dict[int, deque] = {}
        self._max_track_history_len: int = 15
        self._counted_tracks: dict[int, dict] = {}
        self._frame: np.ndarray | None = None
        self._last_count_payload: dict | None = None
        self.running: bool = True
        self.paused = False

        # Load and initialize config
        self.__initialize_config(location, config_manager, kwargs)

        # Init logger
        self.logger: Logger = Logger()

        # Aggregate frame and inference timings of the counting loop, per telemetry window
        self.perf: PerfReporter = PerfReporter(self.settings)

        # Outward events: an injected sink, or Socket.IO through NotificationManager.
        if event_sink is None:
            from system.managers.notification_manager import NotificationManager
            from system.services.counter_events import NotificationEventSink
            event_sink = NotificationEventSink(NotificationManager(socketio=socketio, location=location))
        self.events: CountingEventSink = event_sink

        # Count persistence: an injected store, or the shared DatabaseManager.
        if store is None:
            db_manager = kwargs.get('db_manager')
            if db_manager:
                from system.services.count_store import DatabaseCountStore
                store = DatabaseCountStore(db_manager)
        self.store: CountStore | None = store

        # Initialize video stream manager
        self.vsm: VideoStreamManager = VideoStreamManager(
            self.video_path,
            self.video_fps,
            max_reconnect_attempts=self.video_reconnect_attempts,
        )
        if not self.vsm.connect_with_retries():
            raise StreamConnectionError(f"Cannot open video stream: {self.video_path}")

        # Overlay drawing: reads settings live, so a zone change redraws on the next frame.
        # The camera FPS lookup is lazy — a stream that cannot report it must not break
        # construction, and the HUD already swallows that failure per frame.
        self.renderer: FrameRenderer = FrameRenderer(
            self.settings, self._class_label, lambda: self.vsm.get_actual_fps(),
        )

        # Preview stream for the browser; it reads the running flag to know when to wind down.
        self.stream: MjpegBroadcaster = MjpegBroadcaster(
            self.settings, self.logger, lambda: self.running,
        )

        # Init recorder (async video writer) if enabled for this detection
        self.rec: RecordingControl = RecordingControl(self.settings, self.logger)
        self.rec.init_recorder()

        # Dataset frame saving: instant capture, probability samples and interval capture.
        # The source-frame lookup is lazy so a capture request always sees the newest frame.
        self.capture: DatasetCapture = DatasetCapture(
            self.settings, self.logger, config_manager, lambda: self.get_source_frame(),
        )

        # Model and preview mode state
        self.preview_mode: bool = False

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
                active_class_ids = self.settings.active_class_ids()
                classes_list = active_class_ids or None
                self.model = load_detector(
                    architecture=self.model_type,
                    weights=self.weights,
                    confidence=self.confidence,
                    iou=self.iou,
                    device=self.device,
                    vid_stride=self.vid_stride,
                    classes_list=classes_list,
                    verbose=self.debug,
                    input_size=self.input_size,
                    providers=self.providers,
                )
            except Exception as e:
                self.logger.warning(
                    f"Could not load detector for '{self.location}': {e}. Falling back to Data Collection mode."
                )
                self.model = None
                self.preview_mode = True

        self.tracker = self._new_tracker()

        # Per-frame pipeline; run_frames() hands the thread to it and it reads back
        # through this counter, so there is one copy of every value.
        self.loop: CounterLoop = CounterLoop(self)

    @property
    def lock(self) -> threading.RLock:
        """Synchronization lock protecting shared counter state."""
        return self._lock

    @property
    def generation(self) -> int:
        """Monotonically increasing generation version for tracking resets."""
        with self._lock:
            return self._generation

    def set_frame(self, value: np.ndarray | None, copy: bool = True) -> None:
        """
        Set the current annotated frame.

        Args:
            value: The frame to store.
            copy: If True, copies the buffer for safe isolation.
                  If False (used by CounterLoop), transfers ownership of an
                  already-owned, freshly-rendered frame without an extra copy.
        """
        with self._lock:
            if value is None:
                self._frame = None
            else:
                self._frame = value.copy() if copy else value

    @property
    def frame(self) -> np.ndarray | None:
        """Latest annotated frame produced by the counter loop (isolated copy)."""
        with self._lock:
            if self._frame is not None:
                return self._frame.copy()
            return None

    @frame.setter
    def frame(self, value: np.ndarray | None) -> None:
        self.set_frame(value, copy=True)

    def get_annotated_frame(self) -> Optional[np.ndarray]:
        """Return an independent copy of the latest annotated frame under lock."""
        return self.frame

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_frames(self) -> None:
        """
        Run the generation of frames.

        Returns:
            None
        """
        self.loop.run()

    def get_frames(self) -> Generator:
        """
        Generator that yields frames in the form of JPEG images.

        Returns:
            A generator that yields frames in the form of JPEG images.
        """
        return self.stream.frame_stream()

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
        with self._lock:
            class_ids = (
                    set(self.counts.class_counts.keys())
                    | set(self.counts.current_class_counts.keys())
                    | self._configured_class_ids()
            )
            return [
                {
                    'id': class_id,
                    'name': self._class_label(class_id),
                    'total': int(self.counts.class_counts.get(class_id, 0)),
                    'current': int(self.counts.current_class_counts.get(class_id, 0)),
                }
                for class_id in sorted(class_ids)
            ]

    def get_live_counts(self) -> dict:
        """
        Return in-memory counts in the same shape as the Socket.IO payload.

        Returns:
            dict: total, current, defect, correct, pending_defect, pending_correct, by_class
        """
        with self._lock:
            counts = self.counts
            return {
                'total': counts.total_count - counts.defect_count + counts.correct_count,
                'current': counts.current_count,
                'defect': counts.defect_count,
                'correct': counts.correct_count,
                'pending_defect': counts.pending_defect_count,
                'pending_correct': counts.pending_correct_count,
                'by_class': self._by_class_payload(),
            }

    def emit_live_counts(self, force: bool = False) -> None:
        """
        Broadcast current counts to all connected clients.

        Args:
            force (bool): Emit even when the payload is unchanged.
        """
        should_emit = False
        with self._lock:
            payload = self.get_live_counts()
            if force or payload != self._last_count_payload:
                self._last_count_payload = payload
                should_emit = True

        if should_emit:
            self.events.counts(payload)

    def set_pending_counts(self, pending_defect: int, pending_correct: int) -> dict:
        """
        Update unsaved defect / correct keyboard values and broadcast them.

        Args:
            pending_defect (int): Pending defect count.
            pending_correct (int): Pending correct count adjustment.

        Returns:
            dict: Current live counts payload.
        """
        with self._lock:
            self.counts.set_pending(pending_defect, pending_correct)
            payload = self.get_live_counts()
            self._last_count_payload = payload

        self.events.counts(payload)
        return payload

    def get_current_count(self) -> dict:
        """
        Get current count.

        Returns:
            dict: The current count.
        """
        return self.store.get_current(self.location) or {}

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
        with self._lock:
            total_count = int(self.counts.total_count)
            resolved_correct, resolved_defect = self.counts.resolve_adjustment(correct_count, defect_count)
            current_total_count = self.counts.apply_save(resolved_correct, resolved_defect)
            saved_correct = int(self.counts.correct_count)
            saved_defect = int(self.counts.defect_count)
            class_payload = self._by_class_payload()
            self.counts.clear_pending()
            live_payload = self.get_live_counts()
            self._last_count_payload = live_payload

        result = False
        if self.store is not None:
            result = self.store.save_result(
                location=location,
                total_count=current_total_count,
                source_count=total_count,
                correct_count=saved_correct,
                defects_count=saved_defect,
                custom_fields=custom_fields,
                active=active,
                class_counts=class_payload,
            )

        if result:
            self.events.notify(trans('Saved successfully!'), 'success')
        else:
            self.events.notify(trans('Save error!'), 'danger')

        self.events.counts(live_payload)

        return dict(total=total_count, defect=resolved_defect, correct=resolved_correct)

    def reset_count(self, location: str) -> None:
        """
        Resets the count of total objects and total count.

        Args:
            location (str): The location of the object.

        Returns:
            None
        """
        with self._lock:
            final_class_counts = self._by_class_payload()
            self._generation += 1  # Invalidate in-flight detections from prior generation

            self.total_objects.clear()
            self._total_objects_queue.clear()
            self._track_history.clear()
            self._counted_tracks.clear()
            self.counts.reset_counts()
            self.counts.clear_pending()

            # Reset active tracker state so old tracks don't instantly re-trigger
            self.tracker = self._new_tracker()
            live_payload = self.get_live_counts()
            self._last_count_payload = live_payload

        if self.store is not None:
            self.store.close_current(location, class_counts=final_class_counts)

        # Stop the current recording video
        self.rec.stop()

        self.events.notify(trans('Counting completed successfully!'), 'primary')
        self.events.counts(live_payload)

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
        with self._lock:
            current_count = int(self.counts.current_count)
            total_count = int(self.counts.total_count)
            resolved_correct, resolved_defect = self.counts.resolve_adjustment(correct_count, defect_count)
            by_class = self._by_class_payload()

            self.counts.apply_current_reset(resolved_correct, resolved_defect)
            self.counts.clear_pending()
            live_payload = self.get_live_counts()
            self._last_count_payload = live_payload

        if self.store is not None:
            try:
                self.store.save_part_result(
                    location=location,
                    current_count=current_count,
                    total_count=total_count,
                    defects_count=resolved_defect,
                    correct_count=resolved_correct,
                    by_class=by_class,
                    class_counts=by_class,
                )
            except Exception as e:
                print(e)
                self.logger.error(e)

        self.events.counts(live_payload)
        self.events.notify(trans('The counter has been reset!'), 'primary')

    def start(self) -> None:
        """
        Start counting.

        Args:
            None

        Returns:
            None
        """
        was_paused = False
        with self._lock:
            if self.paused:
                was_paused = True
                self.paused = False

        if was_paused:
            self.events.notify(trans('Counting has started!'), 'success')
            status_evt = 'collection' if self.preview_mode else 'started'
            self.events.status(status_evt)

    def stop(self) -> None:
        """
        Stop counting.

        Args:
            None

        Returns:
            None
        """
        was_running = False
        with self._lock:
            if self.running:
                was_running = True
                self.running = False

        if was_running:
            self.perf.maybe_report(force=True)
            self.events.notify(trans('Counting has stopped!'), 'primary')
            self.events.status('stopped')

        self.stream.shutdown()

        # Stop the current recording video
        self.rec.stop()

    def pause(self) -> None:
        """
        Pause counting.

        Args:
            None

        Returns:
            None
        """
        was_paused = True
        with self._lock:
            if not self.paused:
                was_paused = False
                self.paused = True

        if not was_paused:
            self.events.notify(trans('Counting has paused!'), 'warning')
            self.events.status('paused')

    def is_pause(self) -> bool:
        """
        Check if the counting is paused.

        Returns:
            bool: True if the counting is paused, False otherwise
        """
        with self._lock:
            return self.paused

    def cached_source_frame(self) -> np.ndarray | None:
        """
        The raw frame the loop is currently working on.
        Always returns an independent copy under lock to ensure caller isolation.

        Returns:
            numpy.ndarray | None: None until the loop has read its first frame.
        """
        with self._lock:
            cached = self.loop.cached_frame
            if cached is None:
                return None
            return cached.copy()

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
        with self._lock:
            cached = self.loop.cached_frame
            if cached is not None:
                return cached.copy()

        try:
            return self.vsm.get_frame()
        except Exception as e:
            self.logger.error(f'Error reading source frame: {e}')
            return None

    def debug_detect(self, frame: np.ndarray) -> np.ndarray:
        """
        Run one detection-and-tracking pass for diagnostics.

        The telemetry doctor times this against a dummy frame to check the model is
        responsive; the counting loop runs the same pass for every real frame.

        Args:
            frame (numpy.ndarray): The frame to detect in.

        Returns:
            ndarray: Tracked boxes [x1, y1, x2, y2, track_id, (optional) class_id].
        """
        return self.loop.detect(frame)

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

        with self._lock:
            settings = self.settings
            settings.counting_areas = runtime
            settings.counting_area = list(runtime[0]['points'])
            settings.counting_area_color = tuple(runtime[0]['color'])
            settings.counting_area_direction = str(runtime[0].get('direction', 'any'))
            self.renderer.invalidate_zones()

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
            else tuple(self.settings.counting_area_color or DEFAULT_COUNTING_AREA_COLOR)
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
        return self.capture.save_capture(target_dataset=target_dataset, split=split)

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
        return self.capture.start_interval(interval_sec, max_frames, target_dataset, split)

    def stop_interval_capture(self) -> dict:
        """
        Stop periodic background frame capturing.
        """
        return self.capture.stop_interval()

    def get_interval_capture_status(self) -> dict:
        """
        Get status of periodic background frame capturing.
        """
        return self.capture.status()

    def cleanup(self) -> None:
        """
        Cleaning resources

        Args:
            None

        Returns:
            None
        """
        self.stop()
        self.rec.stop()
        if hasattr(self, 'vsm') and self.vsm is not None:
            self.vsm.stop()
        if hasattr(self, 'model') and self.model is not None:
            self.model.cleanup()
        if getattr(self, 'store', None) is not None:
            self.store.close()

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
            - self.vid_stride (int): The stride for video processing.
            - self.classes (dict): The classes for object detection.
            - self.dataset (dict): The dataset for creating the object counter.
            - self.video_path (str): The path to the video.
            - self.counts.total_count (int): The total count of objects.
            - self.total_objects (set): The set of total objects.

        Appearance, preview quality and recording parameters are not copied onto the counter
        either: FrameRenderer, MjpegBroadcaster and RecordingControl read them from
        self.settings, so a settings change is live on the next frame.

        If the 'start_total_count' key in the detector_config is greater than 0,
        seeds the counting state and updates the configuration file.
        """

        settings = CounterSettings.from_config(config_manager, location, kwargs)
        self.settings = settings
        settings.apply_to(self)
        self.config_manager: ConfigManager = config_manager

        # Started counter value from config
        start_count: int = settings.start_total_count
        if start_count > 0:
            self.counts.total_count = start_count
            start_ids = range(-start_count, 0)
            self.total_objects = set(start_ids)
            self._total_objects_queue = deque(start_ids, maxlen=self._max_tracked_history)
            config_manager.set(f"detections.{self.location}.start_total_count", 0)
            config_manager.save_config()

    def _new_tracker(self) -> Sort | BYTETracker:
        """
        Build the tracker selected for this camera.

        A track threshold of 0 follows the model confidence. ByteTrack also
        associates boxes between the low threshold and that confident threshold.
        """
        if self.tracker_name == 'bytetrack':
            track_thresh = self.tracker_track_thresh
            if track_thresh <= 0:
                track_thresh = max(0.2, float(self.confidence) * 0.7)
            return BYTETracker(
                track_thresh=track_thresh,
                iou_threshold=self.tracker_iou,
                max_age=self.tracker_max_age,
                min_hits=self.tracker_min_hits,
                low_thresh=self.tracker_low_thresh,
            )
        return Sort(
            max_age=self.tracker_max_age,
            min_hits=self.tracker_min_hits,
            iou_threshold=self.tracker_iou,
        )

    @property
    def indicator_mode(self) -> str:
        """Indicator style currently drawn — the live setting, not a copy."""
        with self._lock:
            return self.settings.indicator_mode

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
            mode = CounterSettings.DEFAULT_INDICATOR_MODE
        with self._lock:
            self.settings.indicator_mode = mode
            return self.settings.indicator_mode

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
        with self._lock:
            settings = self.settings
            if detected_color is not None:
                try:
                    settings.indicator_detected_color = tuple(
                        normalize_color_value(detected_color, 'indicator_detected_color'))
                except Exception as e:
                    self.logger.warning(f"Failed to set indicator_detected_color: {e}")
            if counted_color is not None:
                try:
                    settings.indicator_counted_color = tuple(
                        normalize_color_value(counted_color, 'indicator_counted_color'))
                except Exception as e:
                    self.logger.warning(f"Failed to set indicator_counted_color: {e}")
            return settings.indicator_detected_color, settings.indicator_counted_color
