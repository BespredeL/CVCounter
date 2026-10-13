# -*- coding: utf-8 -*-
import unittest
from app import create_app

class TestSettingsApi(unittest.TestCase):
    def setUp(self):
        self.app, _, _ = create_app(test_config={'TESTING': True, 'SECRET_KEY': 'test-key'})
        self.app.secret_key = 'test-key'
        self.client = self.app.test_client()

    def _login(self):
        with self.client.session_transaction() as sess:
            sess['auth_user'] = 'admin'

    def test_runtimes_status_endpoint(self):
        self._login()
        resp = self.client.get('/settings/api/runtimes/status')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get('ok'))
        self.assertIn('runtimes', data)

    def test_models_list_endpoint(self):
        self._login()
        resp = self.client.get('/settings/api/models/list')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get('ok'))
        self.assertIn('models', data)

    def test_export_status_endpoint(self):
        self._login()
        resp = self.client.get('/settings/api/models/export/status')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get('ok'))
        self.assertIn('export', data)

    def test_logs_endpoint(self):
        self._login()
        resp = self.client.get('/settings/api/logs?lines=20')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get('ok'))
        self.assertIn('lines', data)
        self.assertIn('total_lines', data)
        self.assertIn('file_size_formatted', data)

    def test_logs_download_endpoint(self):
        self._login()
        resp = self.client.get('/settings/api/logs/download')
        # Either 200 with text/plain attachment, or 404 if log file does not exist yet
        self.assertIn(resp.status_code, [200, 404])

if __name__ == '__main__':
    unittest.main()
