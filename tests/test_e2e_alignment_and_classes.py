import os
import json
import tempfile
import unittest
from unittest.mock import patch
from system.object_detection.metadata import extract_model_classes
from system.utils.camera_schema import align_full_config, CANONICAL_CAMERA_KEYS, BACKEND_SPECIFIC_PARAMS
from system.managers.config_manager import ConfigManager
from app import app


class TestE2EAlignmentAndClasses(unittest.TestCase):
    def setUp(self):
        ConfigManager._instance = None
        ConfigManager._init_path = None
        self.app = app
        self.client = app.test_client()

    def tearDown(self):
        ConfigManager._instance = None
        ConfigManager._init_path = None

    def test_extract_classes_from_real_yolov8_model(self):
        real_model_path = os.path.join("config", "ultralytics", "models", "yolov8n.pt")
        if not os.path.exists(real_model_path):
            self.skipTest(f"Model file {real_model_path} not found")

        # 1. Direct extraction
        res = extract_model_classes(real_model_path)
        self.assertIsNotNone(res)
        classes, source = res
        self.assertIsNotNone(classes)
        # Note: classes extracted directly may have integer or string keys
        self.assertEqual(classes.get(0) or classes.get("0"), "person")
        self.assertEqual(classes.get(2) or classes.get("2"), "car")

        # 2. Via Flask API endpoint
        with patch("system.auth.auth.get_authenticated_username", return_value="admin"):
            response = self.client.post("/settings/api/model_classes", json={
                "weights_path": real_model_path
            })
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertTrue(data.get("success") or data.get("ok"))
            # API formats keys as string IDs
            self.assertEqual(data.get("classes", {}).get("0"), "person")
            self.assertEqual(data.get("classes", {}).get("2"), "car")

    def test_align_real_config_json(self):
        config_path = os.path.join("config", "config.json")
        if not os.path.exists(config_path):
            self.skipTest("config/config.json not found")

        with open(config_path, "r", encoding="utf-8") as f:
            raw_cfg = json.load(f)

        aligned = align_full_config(raw_cfg)

        # Check detection_default
        if "detection_default" in aligned:
            default_cam = aligned["detection_default"]
            keys = list(default_cam.keys())
            # Canonical keys must appear first in order
            for i, expected_k in enumerate(CANONICAL_CAMERA_KEYS):
                self.assertEqual(keys[i], expected_k)

        # Check all cameras in detections
        if "detections" in aligned and isinstance(aligned["detections"], dict):
            for cam_id, cam_conf in aligned["detections"].items():
                keys = list(cam_conf.keys())
                for i, expected_k in enumerate(CANONICAL_CAMERA_KEYS):
                    self.assertEqual(keys[i], expected_k, f"Camera {cam_id} key mismatch at position {i}")

                # Backend-specific keys check
                m_type = cam_conf.get("model_type")
                if m_type in BACKEND_SPECIFIC_PARAMS:
                    for bp in BACKEND_SPECIFIC_PARAMS[m_type]:
                        self.assertIn(bp, cam_conf, f"Backend param {bp} missing for camera {cam_id}")

    def test_save_from_request_with_classes_and_alignment(self):
        # Test full form handling and alignment via ConfigManager instance
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json', mode='w', encoding='utf-8')
        raw_cfg = {
            "general": {"debug": False},
            "server": {"host": "0.0.0.0", "port": 5000},
            "db": {"uri": "sqlite:///:memory:"},
            "detection_default": {
                "label": "Default",
                "model_type": "yolo"
            },
            "detections": {
                "cam1": {
                    "label": "Camera 1",
                    "model_type": "opencv",
                    "z_custom": "custom_val"
                }
            }
        }
        json.dump(raw_cfg, temp_file)
        temp_file.close()

        try:
            cm = ConfigManager(temp_file.name)
            form_data = {
                "detection_default-label": "Default Cam",
                "detection_default-model_type": "yolo",
                "detection_default-weights_path": "config/ultralytics/models/yolov8n.pt",
                "detection_default-device": "0",
                "detection_default-classes-0-name": "person",
                "detection_default-classes-0-enabled": "on",
                "detection_default-classes-1-name": "bicycle",
                # classes-1-enabled is omitted (unchecked switch)
                "detections-cam1-label": "Camera 1",
                "detections-cam1-model_type": "opencv",
                "detections-cam1-weights_path": "models/cam1.onnx",
                "detections-cam1-classes-0-name": "car",
                "detections-cam1-classes-0-enabled": "on"
            }

            cm.save_from_request(form_data)
            saved = cm.read_config()

            # Verify detection_default
            dd = saved["detection_default"]
            self.assertIn("classes", dd)
            self.assertEqual(dd["classes"]["0"], {"name": "person", "enabled": True})
            self.assertEqual(dd["classes"]["1"], {"name": "bicycle", "enabled": False})

            # Verify cam1 alignment and opencv backend params
            cam1 = saved["detections"]["cam1"]
            self.assertEqual(cam1["model_type"], "opencv")
            self.assertIn("backend", cam1)
            self.assertIn("target", cam1)
            self.assertIn("input_size", cam1)
            self.assertEqual(cam1["classes"]["0"], {"name": "car", "enabled": True})
            self.assertEqual(cam1["z_custom"], "custom_val")
            # Custom key preserved at end
            keys = list(cam1.keys())
            self.assertEqual(keys[-1], "z_custom")
        finally:
            if os.path.exists(temp_file.name):
                os.remove(temp_file.name)


if __name__ == '__main__':
    unittest.main()
