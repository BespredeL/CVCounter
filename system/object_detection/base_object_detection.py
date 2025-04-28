# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 26.12.2024
# Updated: 31.03.2025
# Website: https://bespredel.name


class BaseObjectDetectionService:
    def __init__(self) -> None:
        pass

    def detect(self, image, **kwargs):
        """
        Detects objects in an image using a pre-trained model.

        Args:
            image: The input image.
            **kwargs: Additional keyword arguments.

        Returns:
            ndarray: An array of updated results after tracking the detected objects.
        """

        pass

    def load_model(self, weights: str, **kwargs):
        """
        Loads a pre-trained model for object detection.

        Args:
            weights: The path to the pre-trained model weights file.
            **kwargs: Additional keyword arguments.

        Returns:
            None
        """
        pass

    def cleanup(self):
        """
        Cleaning resources

        Returns:
            None
        """
        pass
