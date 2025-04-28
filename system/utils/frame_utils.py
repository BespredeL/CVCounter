# -*- coding: utf-8 -*-
# ! python3
from typing import Any

# Developed by: Aleksandr Kireev
# Created: 28.04.2025
# Updated: 28.04.2025
# Website: https://bespredel.name

import cv2
from numpy import dtype, ndarray, unsignedinteger

from numpy._typing import _8Bit
from system.utils.exception_handler import FrameEncodingError


class FrameUtils:
    """
    Utility class for various frame (image) operations such as encoding and resizing.

    This class provides static methods to encode image frames into different formats
    and to resize frames by a given scale percentage.
    """

    @staticmethod
    def encoding_frame(frame: cv2.Mat | ndarray, quality: int = 95, ext: str = "jpg") -> bytes:
        """
        Encodes the frame in the specified format.

        Args:
            frame (cv2.Mat): Image frame to encode.
            quality (int): Compression quality (default is 95).
            ext (str): Output file extension/format (e.g., 'jpg', 'png').

        Returns:
            bytes: Encoded frame as a byte string.

        Raises:
            FrameEncodingError: If the frame could not be encoded.
        """
        ext = ext if ext.startswith(".") else "." + ext
        ret, frame_encoded = cv2.imencode(ext, frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if not ret:
            raise FrameEncodingError("Failed to encode frame")
        return frame_encoded

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
        width = int(frame.shape[1] * scale_percent / 100)
        height = int(frame.shape[0] * scale_percent / 100)
        return cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
