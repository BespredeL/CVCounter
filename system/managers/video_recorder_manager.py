# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 22.05.2025
# Updated: 22.05.2025
# Website: https://bespredel.name

import threading
import time

import cv2


class VideoRecorderManager:
    def __init__(self, stream_manager, output_path, codec='mp4v', fps=20.0, resolution=(640, 480)):
        self.stream_manager = stream_manager
        self.output_path = output_path
        self.codec = codec
        self.fps = fps
        self.resolution = resolution

        self.recording = False
        self.writer = None
        self.thread = None
        self.stop_event = threading.Event()

    def start_recording(self):
        if not self.recording:
            fourcc = cv2.VideoWriter_fourcc(*self.codec)
            self.writer = cv2.VideoWriter(self.output_path, fourcc, self.fps, self.resolution)
            self.stop_event.clear()
            self.thread = threading.Thread(target=self._record, daemon=True)
            self.thread.start()
            self.recording = True

    def write(self, frame):
        if self.recording and self.writer is not None:
            resized_frame = cv2.resize(frame, self.resolution)
            self.writer.write(resized_frame)

    def _record(self):
        while not self.stop_event.is_set():
            frame = self.stream_manager.get_frame()
            if frame is not None:
                resized_frame = cv2.resize(frame, self.resolution)
                self.writer.write(resized_frame)
            time.sleep(1 / self.fps)

    def stop_recording(self):
        if self.recording:
            self.stop_event.set()
            self.thread.join()
            self.writer.release()
            self.writer = None
            self.recording = False

    def is_recording(self):
        return self.recording
