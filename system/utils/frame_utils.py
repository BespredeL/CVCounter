# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

import cv2
from numpy import ndarray

from system.utils.exception_handler import FrameEncodingError


class FrameUtils:
    """
    Utility class for various frame (image) operations such as encoding and resizing.

    This class provides static methods to encode image frames into the bytes the
    HTTP responses and the MJPEG stream are built from, and to resize frames by a
    given scale percentage.
    """

    @staticmethod
    def encode_jpeg(frame: cv2.Mat | ndarray, quality: int) -> bytes:
        """
        Encodes the frame as a JPEG image.

        Args:
            frame (cv2.Mat | ndarray): Image frame to encode.
            quality (int): JPEG compression quality (1-100).

        Returns:
            bytes: Encoded frame as a byte string.

        Raises:
            FrameEncodingError: If the frame could not be encoded.
        """
        ret, frame_encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if not ret:
            raise FrameEncodingError("Failed to encode frame")
        return frame_encoded.tobytes()

    @staticmethod
    def multipart_chunk(jpeg: bytes) -> bytes:
        """
        Wraps an encoded JPEG as one part of a multipart MJPEG stream.

        Args:
            jpeg (bytes): Encoded JPEG image.

        Returns:
            bytes: Chunk to yield from the stream generator.
        """
        return (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n'
                + jpeg
                + b'\r\n'
        )

    @staticmethod
    def resize_frame(frame: cv2.Mat | ndarray, scale_percent: int = 70) -> cv2.Mat:
        """
        Resizes the frame according to the specified scale percentage.

        Args:
            frame (cv2.Mat or ndarray): Image frame to resize.
            scale_percent (int): Percentage of the original size (default is 70).

        Returns:
            cv2.Mat: Resized image frame.
        """
        if scale_percent >= 100:
            return frame

        width = max(1, int(frame.shape[1] * scale_percent / 100))
        height = max(1, int(frame.shape[0] * scale_percent / 100))
        if width == frame.shape[1] and height == frame.shape[0]:
            return frame
        # INTER_LINEAR is much cheaper than INTER_AREA on a live preview.
        return cv2.resize(frame, (width, height), interpolation=cv2.INTER_LINEAR)
