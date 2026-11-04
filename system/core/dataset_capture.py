# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

"""Frame saving for dataset building: instant capture, probability sampling and interval capture."""

from __future__ import annotations

import os
import random
import re
import time
from collections.abc import Callable
from pathlib import Path

import cv2
import numpy as np

from system.core.counter_config import CounterSettings
from system.managers.config_manager import ConfigManager
from system.utils.logger import Logger


class DatasetCapture:
    """
    Writes overlay-free frames to disk for dataset building.

    Three policies share one writer: an instant capture requested by the UI, a random
    sample taken when the total count changes, and an interval capture that runs until
    it reaches its frame budget. Sample targets are either a named dataset under
    storage/datasets/<name>/images/<split> or the location folder from the dataset config.
    """

    DEFAULT_JPEG_QUALITY: int = 90
    DEFAULT_INTERVAL: float = 3.0
    DEFAULT_MAX_FRAMES: int = 50
    DEFAULT_SPLIT: str = 'inbox'
    DEFAULT_SAMPLE_PROBABILITY: float = 0.1
    MIN_INTERVAL: float = 0.2

    def __init__(
            self,
            settings: CounterSettings,
            logger: Logger,
            config_manager: ConfigManager,
            source_frame: Callable[[], np.ndarray | None],
    ) -> None:
        """
        Args:
            settings (CounterSettings): Live configuration; the dataset block is read per call.
            logger (Logger): Where write failures are reported.
            config_manager (ConfigManager): Resolves relative dataset paths to the project.
            source_frame (Callable): Returns the raw frame an instant capture should store.
        """
        self.settings = settings
        self.logger = logger
        self.config_manager = config_manager
        self.source_frame = source_frame

        self.active: bool = False
        self.interval: float = DatasetCapture.DEFAULT_INTERVAL
        self.max_frames: int = DatasetCapture.DEFAULT_MAX_FRAMES
        self.count: int = 0
        self.target_dataset: str | None = None
        self.split: str = DatasetCapture.DEFAULT_SPLIT
        self._last_capture_time: float = 0.0

    @property
    def dataset(self) -> dict:
        """The dataset_create block of this location, read live from the settings."""
        return self.settings.dataset

    @property
    def dataset_enabled(self) -> bool:
        """Whether frames should be sampled into the dataset while counting."""
        return bool(self.dataset.get('enable', False))

    def save_capture(self, target_dataset: str | None = None, split: str = 'inbox') -> str | None:
        """
        Save a captured image directly or to a dataset.

        Args:
            target_dataset: Optional dataset name.
            split: Dataset split ('inbox', 'train', 'val').

        Returns:
            str | None: Saved file path or None on failure.
        """
        try:
            frame = self.source_frame()
            if frame is not None:
                return self.save_image(frame, target_dataset=target_dataset, split=split)
        except Exception as e:
            self.logger.error(f'Error saving captured image: {e}')
        return None

    def save_sample(self, frame: np.ndarray, boxes: list | np.ndarray = None) -> str | None:
        """
        Store a frame with the configured probability, filtered by the dataset classes.

        The caller decides when a sample is worth taking; this only applies the random
        gate from the dataset config.

        Args:
            frame (numpy.ndarray): Raw frame from the counting loop.
            boxes: Detected objects used for the class filter.

        Returns:
            str | None: Saved file path, or None when skipped or failed.
        """
        if random.random() < float(self.dataset.get('probability', self.DEFAULT_SAMPLE_PROBABILITY)):
            return self.save_image(frame, boxes, self.dataset.get('classes', None))
        return None

    def start_interval(
            self,
            interval_sec: float = 2.0,
            max_frames: int = 30,
            target_dataset: str | None = None,
            split: str = 'inbox',
    ) -> dict:
        """
        Start periodic background frame capturing.
        """
        self.interval = max(self.MIN_INTERVAL, float(interval_sec))
        self.max_frames = max(1, int(max_frames))
        self.target_dataset = target_dataset
        self.split = split
        self.count = 0
        self._last_capture_time = time.monotonic()
        self.active = True
        return self.status()

    def stop_interval(self) -> dict:
        """
        Stop periodic background frame capturing.
        """
        self.active = False
        return self.status()

    def status(self) -> dict:
        """
        Get status of periodic background frame capturing.
        """
        return {
            'active': bool(self.active),
            'count': int(self.count),
            'max_frames': int(self.max_frames),
            'interval': float(self.interval),
            'dataset': self.target_dataset,
            'split': self.split,
        }

    def maybe_capture_interval(self, frame: np.ndarray) -> None:
        """
        Store one frame if the interval elapsed, and wind down once the budget is spent.

        Args:
            frame (numpy.ndarray): Raw frame from the counting loop.

        Returns:
            None
        """
        if not self.active:
            return

        now = time.monotonic()
        if now - self._last_capture_time < self.interval:
            return

        self._last_capture_time = now
        if self.save_image(frame, target_dataset=self.target_dataset, split=self.split):
            self.count += 1
            if self.count >= self.max_frames:
                self.active = False

    def save_image(
            self,
            frame: np.ndarray,
            boxes: list | np.ndarray = None,
            classes_to_save: dict = None,
            target_dataset: str | None = None,
            split: str = 'inbox',
    ) -> str | None:
        """
        Saves a raw image frame to the dataset or storage path (without overlays or detection marks).

        Args:
            frame (numpy.ndarray): Original BGR frame to be saved.
            boxes: Detected objects used only for optional class filtering.
            classes_to_save: Optional class filter from dataset config.
            target_dataset: Optional dataset name to save into storage/datasets/<name>/images/<split>.
            split: Dataset split ('inbox', 'train', 'val').

        Returns:
            str | None: Saved file path or None on failure.
        """
        if frame is None:
            return None

        try:
            from system.utils.paths import get_project_root, resolve_project_path
            if target_dataset:
                root_path = Path(get_project_root())
                dataset_path = str(root_path / 'storage' / 'datasets' / target_dataset / 'images' / split)
            else:
                raw_path = self.dataset.get('path') if isinstance(self.dataset, dict) else None
                if not raw_path:
                    raw_path = 'storage/saved_images'
                if self.config_manager and hasattr(self.config_manager, 'resolve_path'):
                    base_dir = self.config_manager.resolve_path(raw_path)
                else:
                    base_dir = str(resolve_project_path(raw_path))

                safe_loc = re.sub(r'[^A-Za-z0-9-_]+', '', self.settings.location)
                loc_key = safe_loc or self.settings.location
                norm_base = base_dir.replace('\\', '/').rstrip('/')
                if norm_base.endswith(f'/{loc_key}') or norm_base.endswith(f'/{self.settings.location}'):
                    dataset_path = base_dir
                else:
                    dataset_path = os.path.join(base_dir, loc_key)

            if classes_to_save and boxes is not None and len(boxes) > 0:
                detected_classes = [int(result[-1]) for result in boxes]
                if not any(str(cls) in classes_to_save for cls in detected_classes):
                    return None

            os.makedirs(dataset_path, exist_ok=True)

            location_clean = re.sub(r'[^A-Za-z0-9-_]+', '', self.settings.location)
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
