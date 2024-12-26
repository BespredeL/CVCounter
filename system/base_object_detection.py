# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 26.12.2024
# Updated: 26.12.2024
# Website: https://bespredel.name


class BaseObjectDetectionService:
    def __init__(self) -> None:
        pass

    def detect(self, **kwargs):
        """
        Detects objects in an image using a pre-trained model.

        Args:
            **kwargs: Additional keyword arguments.

        Returns:
            ndarray: An array of updated results after tracking the detected objects.
        """

        pass

    def load_model(self, **kwargs):
        """
        Loads a pre-trained model for object detection.

        Args:
            **kwargs: Additional keyword arguments.

        Returns:
            None
        """
        pass
