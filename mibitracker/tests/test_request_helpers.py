"""Tests for mibitracker.helpers.

This tests for the retry and status checking utilities only.
Specific helper functions that make use of the MibiTracker API and can be
tested by running a local instance of the MibiTracker to ensure proper
integration. A set of examples can be found in
mibitof/notebooks/MibiRequestsTesting.

Copyright (C) 2018 Ionpath, Inc.  All rights reserved.
"""

import io
import os
import shutil
import tempfile
import unittest

from mock import patch
import requests
from requests.exceptions import HTTPError

from mibitracker import request_helpers


class TestMibiRequests(unittest.TestCase):

    def setUp(self):
        self.mock_auth = patch.object(request_helpers.MibiRequests, '_auth')
        self.mock_auth.start()
        self.mtu = request_helpers.MibiRequests(
            'https://mibitracker-instance.ionpath.com',
            'user@ionpath.com',
            'password'
        )

    def tearDown(self):
        self.mock_auth.stop()

    def test_prepare_route(self):
        self.assertEqual(self.mtu._prepare_route('/images/'), '/images/')
        self.assertEqual(self.mtu._prepare_route('images/'), '/images/')

    @patch('requests.Session.get')
    def test_get(self, mock_get):
        self.mtu.get('images', params={'key': 'value'})
        mock_get.assert_called_once_with(
            'https://mibitracker-instance.ionpath.com/images',
            params={'key': 'value'}
        )

    @patch('requests.Session.post')
    def test_post(self, mock_post):
        self.mtu.post('/images/', data={'key': 'value'})
        mock_post.assert_called_once_with(
            'https://mibitracker-instance.ionpath.com/images/',
            data={'key': 'value'}
        )

    @patch('requests.Session.put')
    def test_put(self, mock_put):
        self.mtu.put('/images/1/', data={'key': 'value'})
        mock_put.assert_called_once_with(
            'https://mibitracker-instance.ionpath.com/images/1/',
            data={'key': 'value'}
        )

    @patch('requests.Session.delete')
    def test_delete(self, mock_delete):
        self.mtu.delete('/images/1/')
        mock_delete.assert_called_once_with(
            'https://mibitracker-instance.ionpath.com/images/1/',
        )

    def test_init_sets_retries(self):
        adapter = self.mtu.session.get_adapter(self.mtu.url)
        retries = adapter.max_retries
        self.assertTrue(retries.is_retry('GET', 502))
        self.assertTrue(retries.is_retry('GET', 503))
        self.assertTrue(retries.is_retry('POST', 502))
        self.assertTrue(retries.is_retry('POST', 503))
        self.assertFalse(retries.is_retry('GET', 302))
        self.assertFalse(retries.is_retry('POST', 403))

    @patch('requests.Session.get')
    @patch('requests.Response.raise_for_status')
    def test_status_checks_no_json(self, mock_raise, mock_get):
        mock_raise.side_effect = HTTPError('An HTTP error occurred.')
        mock_get.return_value = requests.Response()
        with self.assertRaises(HTTPError) as e:
            self.mtu.session.get('http://example.com')
        self.assertTrue('An HTTP error occurred' in str(e.exception))

    @patch('requests.Session.get')
    @patch('requests.Response.json')
    @patch('requests.Response.raise_for_status')
    def test_status_checks_with_json(self, mock_raise, mock_json, mock_get):
        mock_raise.side_effect = HTTPError('An HTTP error occurred.')
        mock_json.return_value = {'Error': 'Helpful error description'}
        mock_get.return_value = requests.Response()
        with self.assertRaises(HTTPError) as e:
            self.mtu.session.get('http://domain.com')
        self.assertTrue('An HTTP error occurred' in str(e.exception))
        self.assertTrue('Helpful error description' in str(e.exception))

    @patch('requests.Response.raise_for_status')
    def test_status_checks_other_methods(self, mock_raise):
        mock_raise.side_effect = HTTPError('An HTTP error occurred.')
        for method in ('post', 'put', 'delete'):
            with patch.object(requests.Session, method) as mock_method:
                mock_method.return_value = requests.Response()
                method_to_call = getattr(self.mtu.session, method)
                with self.assertRaises(HTTPError):
                    method_to_call('http://example.com')

    @patch.object(request_helpers.MibiRequests, '_upload_channel')
    def test_upload_channel_missing_filename(self, mock_upload):
        buf = io.BytesIO()
        with self.assertRaises(ValueError):
            self.mtu.upload_channel(1, buf)

    @patch.object(request_helpers.MibiRequests, '_upload_channel')
    def test_upload_channel_with_filename(self, mock_upload):
        buf = io.BytesIO()
        self.mtu.upload_channel(1, buf, filename='image.png')
        mock_upload.assert_called_once_with(1, buf, 'image.png')

    @patch.object(request_helpers.MibiRequests, '_upload_channel')
    def test_upload_channel_use_filename(self, mock_upload):
        folder = tempfile.mkdtemp()
        path = os.path.join(folder, 'image.tiff')
        try:
            with open(path, 'w'):
                pass
            self.mtu.upload_channel(1, path)
        finally:
            shutil.rmtree(folder)
        mock_upload.assert_called_once()
        self.assertEqual(mock_upload.call_args[0][2], 'image.tiff')

    @patch.object(request_helpers.MibiRequests, '_upload_channel')
    def test_upload_channel_custom_filename(self, mock_upload):
        path = 'image.tiff'
        with open(path, 'w'):
            self.mtu.upload_channel(1, path, filename='image.png')
        os.remove(path)
        mock_upload.assert_called_once()
        self.assertEqual(mock_upload.call_args[0][2], 'image.png')

    @patch.object(request_helpers.MibiRequests, '_upload_channel')
    def test_upload_channel_file_object_with_name(self, mock_upload):
        path = 'image.tiff'
        with open(path, 'w') as fh:
            self.mtu.upload_channel(1, fh)
        os.remove(path)
        mock_upload.assert_called_once_with(1, fh, 'image.tiff')

    @patch('requests.Session.post')
    def test_upload_channel(self, mock_post):
        buf = io.BytesIO()
        self.mtu._upload_channel(1, buf, 'image.tiff')

        expected_files = {
            'attachment': ('image.tiff', buf, 'image/tiff')
        }
        mock_post.assert_called_once_with(
            'https://mibitracker-instance.ionpath.com/upload_channel/',
            data={'image_id': 1},
            files=expected_files,
        )
