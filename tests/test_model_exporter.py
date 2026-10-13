# -*- coding: utf-8 -*-
import unittest
from pathlib import Path
from system.utils.model_exporter import ModelExportManager

class TestModelExporter(unittest.TestCase):
    def setUp(self):
        self.manager = ModelExportManager()

    def test_validate_unsupported_format(self):
        res = self.manager.start_export('dummy.pt', 'unknown_format')
        self.assertFalse(res['ok'])
        self.assertIn('format', res['error'].lower())

    def test_validate_nonexistent_weights(self):
        res = self.manager.start_export('nonexistent_path_xyz.pt', 'onnx')
        self.assertFalse(res['ok'])
        self.assertIn('not found', res['error'].lower())

    def test_initial_job_status_idle(self):
        status = self.manager.get_export_status()
        self.assertEqual(status['status'], 'idle')

if __name__ == '__main__':
    unittest.main()
