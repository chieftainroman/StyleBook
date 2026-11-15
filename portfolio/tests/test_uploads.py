"""
Tests for photo and file uploads.

Cloudinary is never called for real in tests: `mock.patch` swaps
`cloudinary.uploader.upload` for a fake that returns what we tell it to.
That keeps tests fast, free, and working without internet.
"""
import base64
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from core.factories import make_master

FAKE_URL = 'https://res.cloudinary.com/demo/image/upload/v1/photo.jpg'
PNG_DATA_URL = 'data:image/png;base64,' + base64.b64encode(b'\x89PNG fake bytes').decode()


def cloudinary_ok(url=FAKE_URL):
    return mock.patch('cloudinary.uploader.upload', return_value={'secure_url': url})


def cloudinary_down():
    return mock.patch('cloudinary.uploader.upload', side_effect=ConnectionError('cloudinary down'))


class UploadTestCase(TestCase):
    def setUp(self):
        self.master = make_master('ana')
        self.client.force_login(self.master.user)


class AvatarAndCoverTests(UploadTestCase):
    def test_avatar_is_uploaded_and_saved_on_the_profile(self):
        with cloudinary_ok() as upload:
            response = self.client.post('/profile/upload-avatar/', {'image_data': PNG_DATA_URL})
        self.assertEqual(response.json(), {'url': FAKE_URL})
        self.master.refresh_from_db()
        self.assertEqual(self.master.avatar_url, FAKE_URL)
        self.assertEqual(upload.call_args.kwargs['public_id'], f'avatar_{self.master.user.id}')

    def test_cover_is_saved_in_its_own_field(self):
        with cloudinary_ok():
            self.client.post('/profile/upload-cover/', {'image_data': PNG_DATA_URL})
        self.master.refresh_from_db()
        self.assertEqual(self.master.cover_url, FAKE_URL)
        self.assertFalse(self.master.avatar_url)

    def test_missing_or_broken_image_data_is_400(self):
        with cloudinary_ok() as upload:
            self.assertEqual(self.client.post('/profile/upload-avatar/', {}).status_code, 400)
            self.assertEqual(self.client.post('/profile/upload-avatar/', {'image_data': 'abc'}).status_code, 400)
        upload.assert_not_called()

    def test_cloudinary_failure_is_502_and_profile_unchanged(self):
        with cloudinary_down():
            response = self.client.post('/profile/upload-avatar/', {'image_data': PNG_DATA_URL})
        self.assertEqual(response.status_code, 502)
        self.master.refresh_from_db()
        self.assertFalse(self.master.avatar_url)

    def test_cloudinary_returning_no_url_is_502(self):
        with cloudinary_ok(url=None):
            self.assertEqual(self.client.post('/profile/upload-avatar/', {'image_data': PNG_DATA_URL}).status_code, 502)

    def test_get_and_anonymous_are_refused(self):
        self.assertEqual(self.client.get('/profile/upload-avatar/').status_code, 405)
        self.client.logout()
        self.assertTrue(self.client.post('/profile/upload-avatar/')['Location'].startswith('/auth/login/'))


class CertificateFileTests(UploadTestCase):
    def upload(self, name, content, content_type):
        return self.client.post('/profile/upload-cert-file/',
                                {'file': SimpleUploadedFile(name, content, content_type=content_type)})

    def test_pdf_goes_up_as_a_raw_file(self):
        with cloudinary_ok() as upload:
            response = self.upload('cert.pdf', b'%PDF-1.4', 'application/pdf')
        self.assertEqual(response.json(), {'url': FAKE_URL, 'kind': 'pdf'})
        self.assertEqual(upload.call_args.kwargs['resource_type'], 'raw')

    def test_image_goes_up_as_an_image(self):
        with cloudinary_ok():
            self.assertEqual(self.upload('cert.jpg', b'jpeg', 'image/jpeg').json()['kind'], 'image')

    def test_other_file_types_are_refused(self):
        with cloudinary_ok() as upload:
            self.assertEqual(self.upload('virus.exe', b'MZ', 'application/octet-stream').status_code, 400)
        upload.assert_not_called()

    def test_files_over_5_mb_are_refused(self):
        with cloudinary_ok() as upload:
            response = self.upload('big.pdf', b'0' * (5 * 1024 * 1024 + 1), 'application/pdf')
        self.assertEqual(response.status_code, 400)
        upload.assert_not_called()

    def test_no_file_is_400(self):
        self.assertEqual(self.client.post('/profile/upload-cert-file/').status_code, 400)

    def test_cloudinary_failure_is_502(self):
        with cloudinary_down():
            self.assertEqual(self.upload('cert.pdf', b'%PDF', 'application/pdf').status_code, 502)


class HonorAndServicePhotoTests(UploadTestCase):
    def test_honor_image_accepts_images_only(self):
        with cloudinary_ok():
            ok = self.client.post('/profile/upload-honor-image/',
                                  {'file': SimpleUploadedFile('a.png', b'png', content_type='image/png')})
            bad = self.client.post('/profile/upload-honor-image/',
                                   {'file': SimpleUploadedFile('a.pdf', b'pdf', content_type='application/pdf')})
        self.assertEqual(ok.json(), {'url': FAKE_URL})
        self.assertEqual(bad.status_code, 400)

    def test_honor_image_cloudinary_failure_is_502(self):
        with cloudinary_down():
            response = self.client.post('/profile/upload-honor-image/',
                                        {'file': SimpleUploadedFile('a.png', b'png', content_type='image/png')})
        self.assertEqual(response.status_code, 502)

    def test_service_photo_is_uploaded_square(self):
        with cloudinary_ok() as upload:
            response = self.client.post('/profile/service/upload-photo/',
                                        {'file': SimpleUploadedFile('cut.jpg', b'jpg', content_type='image/jpeg')})
        self.assertEqual(response.json(), {'url': FAKE_URL})
        self.assertEqual(upload.call_args.kwargs['transformation'][0]['crop'], 'fill')

    def test_service_photo_refuses_missing_large_or_non_image_files(self):
        with cloudinary_ok() as upload:
            self.assertEqual(self.client.post('/profile/service/upload-photo/').status_code, 400)
            big = SimpleUploadedFile('big.jpg', b'0' * (5 * 1024 * 1024 + 1), content_type='image/jpeg')
            self.assertEqual(self.client.post('/profile/service/upload-photo/', {'file': big}).status_code, 400)
            pdf = SimpleUploadedFile('menu.pdf', b'pdf', content_type='application/pdf')
            self.assertEqual(self.client.post('/profile/service/upload-photo/', {'file': pdf}).status_code, 400)
        upload.assert_not_called()
