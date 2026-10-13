# -*- coding: utf-8 -*-
import unittest
from system.utils.runtimes import get_runtime_status, PACKAGE_BUNDLES, RuntimeManager

class TestRuntimes(unittest.TestCase):
    def test_package_bundles_exist(self):
        self.assertIn('onnx_export', PACKAGE_BUNDLES)
        self.assertIn('tensorrt', PACKAGE_BUNDLES)

    def test_get_runtime_status_structure(self):
        status = get_runtime_status()
        self.assertIn('onnx', status)
        self.assertIn('tensorrt', status)
        self.assertIn('gpu', status)
        self.assertIn('packages', status)

    def test_runtime_manager_job_status_idle(self):
        manager = RuntimeManager()
        job = manager.get_install_status()
        self.assertEqual(job['status'], 'idle')

if __name__ == '__main__':
    unittest.main()
