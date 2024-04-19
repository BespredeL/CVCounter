# -*- coding: utf-8 -*-
# ! python3

# Developed by: Alexander Kireev
# Created: 26.03.2024
# Updated: 19.04.2024
# Website: https://bespredel.name

import time

from imutils.video import VideoStream


class VideoStreamManager:
    def __init__(self, video_stream):
        self.__video_stream = video_stream
        self.__cap = None

    """
    Starts the video stream.

    Parameters:
        None
        
    Returns:
        None
    """

    def start(self):
        if not self.is_stream():
            self.__cap = self.__video_stream
        else:
            self.__cap = VideoStream(self.__video_stream).start()

    """
    A method to stop the video capture, if it's currently active.
    
    Parameters:
        None
    
    Returns:
        None
    """

    def stop(self):
        if self.__cap is not None:
            self.__cap.stop()
            self.__cap = None

    """
    Check if the video stream is a valid stream by verifying if it starts with common protocols.
    
    Parameters:
        None
    
    Returns:
        bool: True if the video stream is a valid stream, False otherwise
    """

    def is_stream(self):
        return self.__video_stream.lower().startswith(('rtsp://', 'rtmp://', 'http://', 'https://', 'tcp://'))

    """
    A method to retrieve a frame using the 'cap' attribute.
    
    Parameters:
        None
    
    Returns:
        frame: A frame from the video stream
    """

    def get_frame(self):
        frame = None
        if self.__cap is not None:
            frame = self.__cap.read()
        return frame

    """
    Reconnects to the video stream
    
    Parameters:
        None
    
    Returns:
        None
    """

    def reconnect(self):
        self.stop()
        time.sleep(5)
        self.start()
