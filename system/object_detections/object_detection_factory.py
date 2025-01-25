from system.config_manager import ConfigManager
from system.exception_handler import ModelLoadingError
from system.object_detections.base_object_detection import BaseObjectDetectionService
from system.object_detections.object_detection_yolov7 import ObjectDetectionYOLOv7
from system.object_detections.object_detection_ssd import ObjectDetectionSSD


class ObjectDetectionFactory:
    @staticmethod
    def create_model(config: ConfigManager) -> BaseObjectDetectionService:
        """
        Factory method to create and return an object detection model based on the config file.

        Args:
            config (ConfigManager): The configuration object.

        Returns:
            BaseObjectDetectionService: An instance of the object detection model.
        """
        try:
            model_name = config.get('model_name')
            weights = config.get('weights_path')
            device = config.get('device', 'cpu')
            confidence = config.get('confidence', config.get('detection_default.confidence', 0.5))
            iou = config.get('iou', config.get('detection_default.iou', 0.7))
            classes_list = config.get('classes', {})

            # Создаём модель в зависимости от имени модели
            if model_name == "YOLOv7":
                model = ObjectDetectionYOLOv7()
                model.load_model(weights=weights, device=device)
            elif model_name == "SSD":
                model = ObjectDetectionSSD()  # Допустим, у нас есть класс SSD
                model.load_model(weights=weights, device=device)
            else:
                raise ModelLoadingError(f"Unsupported model: {model_name}")

            # Настроим пороги для детекции
            model.confidence = confidence
            model.iou = iou
            model.classes_list = classes_list

            return model

        except Exception as e:
            raise ModelLoadingError(f"Error loading model: {e}")
