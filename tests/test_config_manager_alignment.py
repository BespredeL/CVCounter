# -*- coding: utf-8 -*-
import unittest
import tempfile
import json
import os
from system.managers.config_manager import ConfigManager

class TestConfigManagerAlignment(unittest.TestCase):
    def setUp(self):
        ConfigManager._instance = None
        ConfigManager._init_path = None
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json', mode='w', encoding='utf-8')
        raw_cfg = {
            "general": {"debug": True},
            "server": {"port": 8080},
            "db": {"uri": "sqlite:///:memory:"},
            "detection_default": {
                "confidence": 0.5,
                "model_type": "yolo"
            },
            "detections": {
                "cam1": {
                    "weights_path": "models/yolo.pt",
                    "label": "Cam 1",
                    "z_custom": 123
                }
            }
        }
        json.dump(raw_cfg, self.temp_file)
        self.temp_file.close()

    def tearDown(self):
        ConfigManager._instance = None
        ConfigManager._init_path = None
        if os.path.exists(self.temp_file.name):
            os.remove(self.temp_file.name)

    def test_startup_alignment(self):
        cm = ConfigManager(self.temp_file.name)
        cfg = cm.read_config()
        cam1 = cfg["detections"]["cam1"]
        keys = list(cam1.keys())
        self.assertEqual(keys[0], "label")
        self.assertEqual(keys[-1], "z_custom")
        self.assertIn("video_show_scale", cam1)

    def test_save_from_request_structured_classes(self):
        cm = ConfigManager(self.temp_file.name)
        form_data = {
            "detections-cam1-classes-0-name": "Person",
            "detections-cam1-classes-0-enabled": "on",
            "detections-cam1-classes-1-name": "Car",
            # detections-cam1-classes-1-enabled is missing because unchecked in HTML
        }
        cm.save_from_request(form_data)
        updated = cm.read_config()["detections"]["cam1"]["classes"]
        self.assertEqual(updated["0"], {"name": "Person", "enabled": True})
        self.assertEqual(updated["1"], {"name": "Car", "enabled": False})

        # Check that saved config is canonically aligned
        keys = list(cm.read_config()["detections"]["cam1"].keys())
        self.assertEqual(keys[0], "label")
        self.assertEqual(keys[-1], "z_custom")

if __name__ == '__main__':
    unittest.main()
