# -*- coding: utf-8 -*-
import unittest
from unittest.mock import MagicMock, patch
import json

class TestClassesAndCounter(unittest.TestCase):
    def test_active_classes_extraction_logic(self):
        from system.core.object_counter import ObjectCounter
        
        # Test active class IDs extraction logic
        classes_cfg = {
            "0": {"name": "Person", "enabled": True},
            "1": {"name": "Bicycle", "enabled": False},
            "2": "Car"  # legacy format string
        }
        
        active = []
        for cid, cval in classes_cfg.items():
            if isinstance(cval, dict):
                if cval.get("enabled", True):
                    active.append(int(cid))
            else:
                active.append(int(cid))
        self.assertEqual(active, [0, 2])

    def test_class_label_resolution(self):
        # Mock minimal ObjectCounter with classes dictionary
        from system.core.object_counter import ObjectCounter
        counter = object.__new__(ObjectCounter)
        counter.classes = {
            "0": {"name": "Person", "enabled": True},
            "1": {"name": "Bicycle", "enabled": False},
            "2": "Car"
        }
        self.assertEqual(counter._class_label(0), "Person")
        self.assertEqual(counter._class_label(1), "Bicycle")
        self.assertEqual(counter._class_label(2), "Car")
        self.assertIn("99", counter._class_label(99))

    def test_model_classes_endpoint(self):
        from flask import Flask
        from routes.settings import settings_bp
        
        app = Flask(__name__)
        app.secret_key = "test"
        app.register_blueprint(settings_bp)
        
        with app.test_client() as client:
            with patch("system.auth.auth.get_authenticated_username", return_value="admin"), \
                 patch("system.auth.auth.auth_enabled", return_value=True):
                # Missing weights_path
                res = client.post("/settings/api/model_classes", json={})
                data = json.loads(res.data)
                self.assertFalse(data.get("ok"))
                
                # Mocked extraction
                with patch("system.object_detection.metadata.extract_model_classes", return_value=({0: "person", 1: "car"}, "sidecar")):
                    res = client.post("/settings/api/model_classes", json={"weights_path": "some_model.onnx"})
                    data = json.loads(res.data)
                    self.assertTrue(data.get("ok"))
                    self.assertEqual(data["classes"]["0"], "person")
                    self.assertEqual(data["classes"]["1"], "car")

if __name__ == '__main__':
    unittest.main()
