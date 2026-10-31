# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

"""The browser preview stream: viewer refcount, background JPEG encoder and MJPEG chunks."""

from __future__ import annotations

import queue
import threading
import time
from collections.abc import Callable, Generator

import numpy as np

from system.core.counter_config import CounterSettings
from system.core.label_render import placeholder_mjpeg_chunk
from system.utils.frame_utils import FrameUtils
from system.utils.logger import Logger


class MjpegBroadcaster:
    """
    Publishes the latest encoded frame to every browser watching a counter.

    The counting thread offers frames through `maybe_encode`; a worker thread encodes
    the newest one so JPEG of a full-size frame never stalls the camera reader.
    `frame_stream` is what the HTTP generator hands to the client.
    """

    POLL_SLEEP: float = 0.01
    DEFAULT_MJPEG_FPS: float = 25.0
    ENCODE_QUEUE_SIZE: int = 1
    ENCODE_POLL_TIMEOUT: float = 0.2

    def __init__(
            self,
            settings: CounterSettings,
            logger: Logger,
            keep_alive: Callable[[], bool],
    ) -> None:
        """
        Args:
            settings (CounterSettings): Live configuration; scale and quality are read
                per frame, so a settings change applies to the next encode.
            logger (Logger): Where encode failures are reported.
            keep_alive (Callable[[], bool]): False once the counter loop has to end.
        """
        self.settings = settings
        self.logger = logger
        self.keep_alive = keep_alive

        self.chunk: bytes | None = None
        self.watching: bool = False
        self.out_fps: float = 0.0

        self._viewers: int = 0
        self._last_encode_time: float = 0.0
        self._out_count: int = 0
        self._out_tick: float = time.monotonic()
        self._encode_queue: queue.Queue | None = None
        self._encode_thread: threading.Thread | None = None

    def encode_interval(self) -> float:
        """
        Minimum seconds between MJPEG encodes for the browser stream.

        Returns:
            float: The minimum seconds between MJPEG encodes
        """
        video_fps = self.settings.video_fps
        if video_fps > 0:
            return 1.0 / float(video_fps)
        return 1.0 / self.DEFAULT_MJPEG_FPS

    def frame_stream(self) -> Generator:
        """
        Generator that yields frames in the form of JPEG images.

        JPEG is encoded on the frame loop. This generator only forwards the latest
        chunk so the HTTP worker stays mostly idle.

        Always yields at least one chunk so Werkzeug calls start_response
        before the client disconnects (e.g. quick navigation away from /video).

        Returns:
            A generator that yields frames in the form of JPEG images.
        """
        self._viewers += 1
        self.watching = True
        sent = False
        last_chunk: bytes | None = None
        try:
            while self.keep_alive() or not sent:
                chunk = self.chunk
                if chunk is not None:
                    if chunk is not last_chunk:
                        yield chunk
                        last_chunk = chunk
                        sent = True
                elif not sent:
                    yield placeholder_mjpeg_chunk()
                    sent = True
                time.sleep(self.POLL_SLEEP)
        except GeneratorExit:
            pass
        except Exception as e:
            self.logger.error(f'Error in get_frames: {e}')
        finally:
            self._viewers = max(0, self._viewers - 1)
            if self._viewers == 0:
                self.watching = False
                self.chunk = None

    def maybe_encode(self, frame: np.ndarray) -> None:
        """
        Encode MJPEG only when the stream interval has elapsed.

        Args:
            frame (numpy.ndarray): The frame to process.

        Returns:
            None
        """
        now = time.monotonic()
        if now - self._last_encode_time < self.encode_interval():
            return

        self._ensure_encode_worker()
        try:
            # The loop owns this frame until the next iteration, so the worker can
            # encode it without a second full-size copy.
            self._encode_queue.put_nowait(frame)
        except queue.Full:
            return
        self._last_encode_time = now

    def shutdown(self) -> None:
        """
        Ask the encode worker to finish with the frame it is holding.

        Returns:
            None
        """
        if self._encode_queue is None:
            return
        try:
            self._encode_queue.put_nowait(None)
        except queue.Full:
            pass

    def _ensure_encode_worker(self) -> None:
        """
        Start the preview encoder once.

        JPEG of a 1080p frame takes 30–50 ms. Doing that on the counting thread
        keeps the camera reader from publishing the next picture.
        """
        if self._encode_thread is not None:
            return
        self._encode_queue = queue.Queue(maxsize=self.ENCODE_QUEUE_SIZE)
        self._encode_thread = threading.Thread(
            target=self._encode_worker,
            name=f"mjpeg-{self.settings.location}",
            daemon=True,
        )
        self._encode_thread.start()

    def _encode_worker(self) -> None:
        """Encode the latest queued preview frame without blocking detection."""
        while self.keep_alive():
            try:
                frame = self._encode_queue.get(timeout=self.ENCODE_POLL_TIMEOUT)
            except queue.Empty:
                continue
            if frame is None:
                return
            chunk = self.encode_chunk(frame)
            if chunk is not None:
                self._note_output_frame()
                self.chunk = chunk

    def _note_output_frame(self) -> None:
        """
        Fold the encoded frame into the rolling output FPS shown on the HUD.

        Returns:
            None
        """
        self._out_count += 1
        now = time.monotonic()
        span = now - self._out_tick
        if span >= 0.5:
            self.out_fps = self._out_count / span
            self._out_count = 0
            self._out_tick = now

    def encode_chunk(self, frame: np.ndarray, scaled: bool = False) -> bytes | None:
        """
        Build one multipart JPEG chunk for the browser MJPEG stream.

        Args:
            frame (numpy.ndarray): BGR frame to encode.
            scaled (bool): Frame is already at video_show_scale.

        Returns:
            bytes | None: Encoded multipart chunk or None on failure.
        """
        if frame is None:
            return None

        try:
            if scaled:
                stream_frame = frame
            else:
                stream_frame = FrameUtils.resize_frame(frame, self.settings.video_scale)

            jpeg = FrameUtils.encode_jpeg(stream_frame, self.settings.video_quality)
            return FrameUtils.multipart_chunk(jpeg)
        except Exception as e:
            self.logger.error(f'Error encoding MJPEG chunk: {e}')
            return None
