# -*- coding: utf-8 -*-
# ! python3

# Developed by: Alexander Kireev
# Created: 26.03.2024
# Updated: 26.03.2024
# Website: https://bespredel.name

import time

from imutils.video import VideoStream


class VideoStreamManager:
    def __init__(self, video_stream):
        self.video_stream = video_stream
        self.cap = None

    """
    Starts the video stream.

    Returns:
        None
    """

    def start(self):
        if not self.is_stream():
            self.cap = self.video_stream
        else:
            self.cap = VideoStream(self.video_stream).start()

    """
    A method to stop the video capture, if it's currently active.
    
    Returns:
        None
    """

    def stop(self):
        if self.cap is not None:
            self.cap.stop()
            self.cap = None

    """
    Check if the video stream is a valid stream by verifying if it starts with common protocols.
    
    Returns:
        bool: True if the video stream is a valid stream, False otherwise
    """

    def is_stream(self):
        return self.video_stream.lower().startswith(('rtsp://', 'rtmp://', 'http://', 'https://', 'tcp://'))

    """
    A method to retrieve a frame using the 'cap' attribute.
    
    Returns:
        frame: A frame from the video stream
    """

    def get_frame(self):
        frame = None
        if self.cap is not None:
            frame = self.cap.read()
        return frame

    """
    Reconnects to the video stream
    
    Returns:
        None
    """

    def reconnect(self):
        self.stop()
        time.sleep(5)
        self.start()
