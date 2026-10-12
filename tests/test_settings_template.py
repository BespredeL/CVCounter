import unittest
from flask import Flask, render_template


class TestSettingsTemplateRendering(unittest.TestCase):
    def setUp(self):
        from app import app
        self.app = app
        self.client = app.test_client()

    def test_settings_template_renders_classes_with_dict_and_string(self):
        with self.app.test_request_context('/settings'):
            sample_config = {
                "server": {"host": "0.0.0.0", "port": 5000},
                "detection_default": {
                    "classes": {
                        "0": {"name": "person", "enabled": True},
                        "1": {"name": "bicycle", "enabled": False},
                        "2": "car"  # legacy format
                    },
                    "weights_path": "models/test.pt"
                },
                "detections": {
                    "cam1": {
                        "classes": {
                            "0": {"name": "person", "enabled": True}
                        },
                        "weights_path": "models/test.pt"
                    }
                }
            }
            # Render settings template with sample config
            html = render_template('settings.html', _config=sample_config)
            self.assertIn('btn-load-model-classes', html)
            self.assertIn('btn-enable-all-classes', html)
            self.assertIn('btn-disable-all-classes', html)
            self.assertIn('cv-class-enable-switch', html)
            self.assertIn('person', html)
            self.assertIn('bicycle', html)
            self.assertIn('car', html)


if __name__ == '__main__':
    unittest.main()
