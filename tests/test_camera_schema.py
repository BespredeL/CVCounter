# -*- coding: utf-8 -*-
import unittest
import copy
from system.utils.camera_schema import align_camera_dict, align_full_config, CANONICAL_CAMERA_KEYS

class TestCameraSchema(unittest.TestCase):
    def test_canonical_ordering_and_defaults(self):
        cam = {
            "weights_path": "models/yolo.pt",
            "label": "Test Cam",
            "custom_field": "val"
        }
        defaults = {"confidence": 0.5, "iou": 0.7, "device": 0, "video_show_scale": 70}
        aligned = align_camera_dict(cam, defaults)
        keys = list(aligned.keys())
        self.assertEqual(keys[0], "label")
        self.assertIn("confidence", aligned)
        self.assertEqual(aligned["confidence"], 0.5)
        self.assertEqual(aligned["video_show_scale"], 70)
        self.assertEqual(keys[-1], "custom_field")

    def test_model_type_specific_parameters(self):
        cam_opencv = {"label": "CV Cam", "model_type": "opencv"}
        aligned = align_camera_dict(cam_opencv)
        self.assertIn("input_size", aligned)
        self.assertIn("backend", aligned)
        self.assertIn("target", aligned)

        cam_onnx = {"label": "ONNX Cam", "model_type": "onnx"}
        aligned_onnx = align_camera_dict(cam_onnx)
        self.assertIn("input_size", aligned_onnx)
        self.assertIn("providers", aligned_onnx)

    def test_multiple_custom_fields_alphabetical(self):
        cam = {
            "label": "Cam",
            "z_param": 1,
            "a_param": 2,
            "m_param": 3
        }
        aligned = align_camera_dict(cam)
        keys = list(aligned.keys())
        # Canonical keys come first, then alphabetical custom fields
        self.assertEqual(keys[-3:], ["a_param", "m_param", "z_param"])

    def test_align_full_config(self):
        cfg = {
            "detection_default": {"confidence": 0.6},
            "detections": {"cam1": {"label": "C1", "model_type": "yolo"}}
        }
        aligned_cfg, changed = align_full_config(cfg)
        self.assertTrue(changed)
        self.assertIn("video_show_scale", aligned_cfg["detection_default"])
        self.assertIn("video_show_scale", aligned_cfg["detections"]["cam1"])
        self.assertEqual(list(aligned_cfg["detections"]["cam1"].keys())[0], "label")

if __name__ == '__main__':
    unittest.main()
