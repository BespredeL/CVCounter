# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

"""Per-location counter settings resolved from config, with defaults and validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from system.utils.counting_area import DEFAULT_COUNTING_AREA_COLOR, areas_to_runtime, normalize_counting_areas
from system.utils.validators import normalize_color_value

if TYPE_CHECKING:
    from system.managers.config_manager import ConfigManager

TRACKERS = ('sort', 'bytetrack')
INDICATOR_MODES = ('circle', 'box')


def config_unit(primary: dict, fallback: dict, key: str, default: float) -> float:
    """Read a 0..1 tracker threshold, falling back when the value is unusable."""
    raw = primary.get(key, fallback.get(key, default))
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = float(default)
    if value < 0.0 or value > 1.0:
        value = float(default)
    return value


def config_positive_int(primary: dict, fallback: dict, key: str, default: int) -> int:
    """Read a tracker frame count of at least 1."""
    raw = primary.get(key, fallback.get(key, default))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = int(default)
    if value < 1:
        value = int(default)
    return value


@dataclass
class CounterSettings:
    """
    Resolved configuration for one detection location.

    Values come from `detections.<location>`, falling back to `detection_default`,
    then to the class defaults below. Runtime keyword arguments override the file.
    """

    DEFAULT_CONFIDENCE: float = 0.5
    DEFAULT_IOU: float = 0.7
    DEFAULT_VIDEO_QUALITY: int = 50
    DEFAULT_VIDEO_SCALE: int = 50
    DEFAULT_MAX_AGE: int = 60
    DEFAULT_MIN_HITS: int = 3
    DEFAULT_TRACKER_IOU: float = 0.3
    DEFAULT_TRACK_THRESH: float = 0.0
    DEFAULT_LOW_THRESH: float = 0.1
    DEFAULT_TRACKER: str = 'sort'
    DEFAULT_INDICATOR_SIZE: int = 10
    DEFAULT_INDICATOR_MODE: str = 'circle'
    DEFAULT_INDICATOR_DETECTED_COLOR: tuple[int, int, int] = (255, 0, 255)
    DEFAULT_INDICATOR_COUNTED_COLOR: tuple[int, int, int] = (0, 255, 0)
    DEFAULT_VID_STRIDE: int = 1
    DEFAULT_RECORDING_PATH: str = "storage/saved_recordings"
    DEFAULT_VIDEO_RECONNECT_ATTEMPTS: int = 5

    location: str = ""
    debug: bool = False
    show_fps: bool = False
    model_type: str = 'auto'
    weights: str = ""
    device: str = 'cpu'
    confidence: float = DEFAULT_CONFIDENCE
    iou: float = DEFAULT_IOU
    counting_areas: list = field(default_factory=list)
    counting_area: list[tuple[int, int]] = field(default_factory=list)
    counting_area_color: tuple = tuple(DEFAULT_COUNTING_AREA_COLOR)
    counting_area_direction: str = 'any'
    video_fps: int = 0
    video_reconnect_attempts: int = DEFAULT_VIDEO_RECONNECT_ATTEMPTS
    video_scale: int = DEFAULT_VIDEO_SCALE
    video_quality: int = DEFAULT_VIDEO_QUALITY
    indicator_size: int = DEFAULT_INDICATOR_SIZE
    tracker_name: str = DEFAULT_TRACKER
    tracker_iou: float = DEFAULT_TRACKER_IOU
    tracker_max_age: int = DEFAULT_MAX_AGE
    tracker_min_hits: int = DEFAULT_MIN_HITS
    tracker_track_thresh: float = DEFAULT_TRACK_THRESH
    tracker_low_thresh: float = DEFAULT_LOW_THRESH
    indicator_mode: str = DEFAULT_INDICATOR_MODE
    indicator_detected_color: tuple[int, int, int] = DEFAULT_INDICATOR_DETECTED_COLOR
    indicator_counted_color: tuple[int, int, int] = DEFAULT_INDICATOR_COUNTED_COLOR
    vid_stride: int = DEFAULT_VID_STRIDE
    classes: dict = field(default_factory=dict)
    dataset: dict = field(default_factory=dict)
    model_config_path: str | None = None
    input_size: int | list = 640
    backend: str | None = None
    target: str | None = None
    providers: list | None = None
    video_path: str = ""
    recording_enabled: bool = False
    recording_base_path: str | None = None
    recording_scale: int = 100
    recording_quality: int = 80
    recording_idle_timeout: float = 0.0
    start_total_count: int = 0

    @classmethod
    def from_config(
        cls,
        config_manager: ConfigManager,
        location: str,
        kwargs: dict | None = None,
    ) -> CounterSettings:
        """
        Resolve settings for one location and reload the configuration from disk.

        Args:
            config_manager (ConfigManager): The configuration object.
            location (str): The location of the object counter.
            kwargs (dict, optional): Runtime overrides passed to the counter.

        Returns:
            CounterSettings: The resolved settings.
        """
        kwargs = kwargs or {}
        config_manager.reload_config()
        detector_config = config_manager.get(f"detections.{location}") or {}
        detection_default = config_manager.get("detection_default", {}) or {}

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

        raw_weights = kwargs.get('weights', detector_config.get('weights_path'))
        model_config_path = detector_config.get('model_config_path') or detection_default.get('model_config_path')

        dataset_config = dict(detector_config.get('dataset_create', {}))
        if dataset_config.get('path'):
            dataset_config['path'] = config_manager.resolve_path(dataset_config['path'])

        recording_default = detection_default.get('recording', {})
        recording_config = detector_config.get('recording', {})
        recording_idle_timeout = float(
            recording_config.get('idle_timeout', recording_default.get('idle_timeout', 0))
        )

        raw_det_color = detector_config.get(
            'indicator_detected_color',
            detection_default.get('indicator_detected_color', cls.DEFAULT_INDICATOR_DETECTED_COLOR)
        )
        try:
            indicator_detected_color: tuple[int, int, int] = tuple(
                normalize_color_value(raw_det_color, 'indicator_detected_color')
            )
        except Exception:
            indicator_detected_color = cls.DEFAULT_INDICATOR_DETECTED_COLOR

        raw_cnt_color = detector_config.get(
            'indicator_counted_color',
            detection_default.get('indicator_counted_color', cls.DEFAULT_INDICATOR_COUNTED_COLOR)
        )
        try:
            indicator_counted_color: tuple[int, int, int] = tuple(
                normalize_color_value(raw_cnt_color, 'indicator_counted_color')
            )
        except Exception:
            indicator_counted_color = cls.DEFAULT_INDICATOR_COUNTED_COLOR

        tracker_name = str(
            detector_config.get('tracker', detection_default.get('tracker', cls.DEFAULT_TRACKER))
        ).strip().lower()
        if tracker_name not in TRACKERS:
            tracker_name = cls.DEFAULT_TRACKER

        indicator_mode = str(
            detector_config.get('indicator_mode', detection_default.get("indicator_mode", cls.DEFAULT_INDICATOR_MODE))
        ).strip().lower()
        if indicator_mode not in INDICATOR_MODES:
            indicator_mode = cls.DEFAULT_INDICATOR_MODE

        return cls(
            location=location,
            debug=kwargs.get('debug', config_manager.get('general.debug', False)),
            show_fps=bool(config_manager.get('general.show_fps', False)),
            model_type=str(kwargs.get(
                'model_type',
                detector_config.get('model_type', detection_default.get('model_type', 'auto'))
            ) or 'auto'),
            weights=config_manager.resolve_path(raw_weights) if raw_weights else "",
            device=kwargs.get('device', detector_config.get('device', 'cpu')),
            confidence=kwargs.get(
                'confidence',
                detector_config.get('confidence', detection_default.get('confidence', cls.DEFAULT_CONFIDENCE)),
            ),
            iou=kwargs.get('iou', detector_config.get('iou', detection_default.get('iou', cls.DEFAULT_IOU))),
            counting_areas=runtime_areas,
            counting_area=list(runtime_areas[0]['points']),
            counting_area_color=tuple(runtime_areas[0]['color']),
            counting_area_direction=str(runtime_areas[0].get('direction', 'any')),
            video_fps=detector_config.get('video_fps', detection_default.get("video_fps", 0)) or 0,
            video_reconnect_attempts=int(detector_config.get(
                'video_reconnect_attempts',
                detection_default.get('video_reconnect_attempts', cls.DEFAULT_VIDEO_RECONNECT_ATTEMPTS),
            )),
            video_scale=detector_config.get('video_show_scale',
                                            detection_default.get("video_show_scale", cls.DEFAULT_VIDEO_SCALE)),
            video_quality=detector_config.get('video_show_quality',
                                              detection_default.get("video_show_quality", cls.DEFAULT_VIDEO_QUALITY)),
            indicator_size=detector_config.get('indicator_size',
                                               detection_default.get("indicator_size", cls.DEFAULT_INDICATOR_SIZE)),
            tracker_name=tracker_name,
            tracker_iou=config_unit(detector_config, detection_default, 'tracker_iou', cls.DEFAULT_TRACKER_IOU),
            tracker_max_age=config_positive_int(
                detector_config, detection_default, 'tracker_max_age', cls.DEFAULT_MAX_AGE
            ),
            tracker_min_hits=config_positive_int(
                detector_config, detection_default, 'tracker_min_hits', cls.DEFAULT_MIN_HITS
            ),
            tracker_track_thresh=config_unit(
                detector_config, detection_default, 'tracker_track_thresh', cls.DEFAULT_TRACK_THRESH
            ),
            tracker_low_thresh=config_unit(
                detector_config, detection_default, 'tracker_low_thresh', cls.DEFAULT_LOW_THRESH
            ),
            indicator_mode=indicator_mode,
            indicator_detected_color=indicator_detected_color,
            indicator_counted_color=indicator_counted_color,
            vid_stride=detector_config.get('vid_stride',
                                           detection_default.get("vid_stride", cls.DEFAULT_VID_STRIDE)),
            classes=detector_config.get('classes', {}),
            dataset=dataset_config,
            model_config_path=config_manager.resolve_path(model_config_path),
            input_size=detector_config.get('input_size', detection_default.get('input_size', 640)),
            backend=detector_config.get('backend', detection_default.get('backend')),
            target=detector_config.get('target', detection_default.get('target')),
            providers=detector_config.get('providers', detection_default.get('providers')),
            video_path=kwargs.get('video_path', detector_config.get('video_path', '')),
            recording_enabled=bool(recording_config.get('enable', recording_default.get('enable', False))),
            recording_base_path=config_manager.resolve_path(
                recording_config.get('path', recording_default.get('path', cls.DEFAULT_RECORDING_PATH))),
            recording_scale=int(recording_config.get('scale', recording_default.get('scale', 100))),
            recording_quality=int(recording_config.get('quality', recording_default.get('quality', 80))),
            recording_idle_timeout=recording_idle_timeout if recording_idle_timeout >= 0 else 0.0,
            start_total_count=int(detector_config.get('start_total_count', 0)),
        )

    def apply_to(self, target: Any) -> None:
        """
        Assign every setting onto the counter, under its legacy attribute name.

        The drawing parameters (zones, indicator style, FPS overlay) and the preview
        scale/quality are left out on purpose: FrameRenderer and MjpegBroadcaster read
        them from this settings object, so copying them would create a second value
        that goes stale on a zone or colour change.

        Args:
            target (Any): ObjectCounter instance being configured.

        Returns:
            None
        """
        target.location = self.location
        target.debug = self.debug
        target.model_type = self.model_type
        target.weights = self.weights
        target.device = self.device
        target.confidence = self.confidence
        target.iou = self.iou
        target.video_fps = self.video_fps
        target.video_reconnect_attempts = self.video_reconnect_attempts
        target.tracker_name = self.tracker_name
        target.tracker_iou = self.tracker_iou
        target.tracker_max_age = self.tracker_max_age
        target.tracker_min_hits = self.tracker_min_hits
        target.tracker_track_thresh = self.tracker_track_thresh
        target.tracker_low_thresh = self.tracker_low_thresh
        target.vid_stride = self.vid_stride
        target.classes = self.classes
        target.dataset = self.dataset
        target.model_config_path = self.model_config_path
        target.input_size = self.input_size
        target.backend = self.backend
        target.target = self.target
        target.providers = self.providers
        target.video_path = self.video_path
        target.recording_enabled = self.recording_enabled
        target.recording_base_path = self.recording_base_path
        target.recording_scale = self.recording_scale
        target.recording_quality = self.recording_quality
        target.recording_idle_timeout = self.recording_idle_timeout

    def active_class_ids(self) -> list[int]:
        """
        Class ids to feed the detector, or an empty list when every class is allowed.

        Returns:
            list[int]: Enabled class ids; empty means "no filter".
        """
        active: list[int] = []
        for cls_id, cls_entry in (self.classes or {}).items():
            try:
                cid = int(cls_id)
            except (ValueError, TypeError):
                continue
            if isinstance(cls_entry, dict):
                if cls_entry.get('enabled', True):
                    active.append(cid)
            else:
                active.append(cid)

        if self.classes and active:
            return active
        return []
