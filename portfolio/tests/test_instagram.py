"""
Tests for the Instagram story generator and the portfolio page.

Placid is being replaced, so these cover what users touch (pages load,
form errors, ownership) and the Pillow generator, not Placid's internals.
Placid and Cloudinary are always mocked: tests never call them for real.
"""
import shutil
import tempfile
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from core.factories import make_master
from portfolio import placid
from portfolio.models import PortfolioItem
from portfolio.utils import FORMATS, TEMPLATES, generate_instagram_image

TEMPLATE_ID = placid.TEMPLATES['story'][0]['id']


def jpeg_bytes(size=(600, 800)):
    from io import BytesIO
    buffer = BytesIO()
    Image.new('RGB', size, (120, 80, 60)).save(buffer, 'JPEG')
    return buffer.getvalue()


class TempMediaTestCase(TestCase):
    """Uploaded and generated files go to a temporary folder deleted after the tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media = tempfile.mkdtemp()
        cls.override = override_settings(MEDIA_ROOT=cls.media)
        cls.override.enable()

    @classmethod
    def tearDownClass(cls):
        cls.override.disable()
        shutil.rmtree(cls.media, ignore_errors=True)
        super().tearDownClass()


class PagesTests(TestCase):
    def setUp(self):
        self.master = make_master('ana')
        self.client.force_login(self.master.user)

    def test_instagram_and_portfolio_pages_render(self):
        self.assertTemplateUsed(self.client.get('/instagram/'), 'instagram.html')
        self.assertTemplateUsed(self.client.get('/portfolio/'), 'portfolio.html')

    def test_portfolio_shows_only_your_own_items(self):
        PortfolioItem.objects.create(user=self.master.user, service='Mine', image='a.jpg')
        PortfolioItem.objects.create(user=make_master('ben').user, service='Theirs', image='b.jpg')
        items = self.client.get('/portfolio/').context['portfolio_items']
        self.assertEqual([i.service for i in items], ['Mine'])

    def test_pages_need_login(self):
        self.client.logout()
        for url in ('/instagram/', '/portfolio/'):
            with self.subTest(url=url):
                self.assertTrue(self.client.get(url)['Location'].startswith('/auth/login/'))

    def test_posting_to_the_page_itself_just_redirects(self):
        self.assertRedirects(self.client.post('/instagram/'), '/instagram/', fetch_redirect_response=False)


class GenerateValidationTests(TempMediaTestCase):
    def setUp(self):
        self.master = make_master('ana')
        self.client.force_login(self.master.user)

    def generate(self, **overrides):
        data = {'service': 'Skin fade', 'template': TEMPLATE_ID,
                'photo': SimpleUploadedFile('cut.jpg', jpeg_bytes(), content_type='image/jpeg')}
        data.update(overrides)
        return self.client.post('/instagram/generate/', {k: v for k, v in data.items() if v is not None})

    def test_missing_photo_service_or_template_is_400(self):
        for label, overrides in {'no photo': {'photo': None}, 'no service': {'service': ''},
                                 'no template': {'template': ''}, 'unknown template': {'template': 'nope'}}.items():
            with self.subTest(label):
                self.assertEqual(self.generate(**overrides).status_code, 400)
        self.assertFalse(PortfolioItem.objects.exists())

    def test_placid_job_is_started_and_tracked(self):
        with mock.patch('cloudinary.uploader.upload', return_value={'secure_url': 'https://cdn.test/cut.jpg'}), \
                mock.patch.object(placid, 'create_image', return_value={'id': 77, 'status': 'queued'}):
            data = self.generate().json()
        self.assertEqual(data['status'], 'queued')
        item = PortfolioItem.objects.get(pk=data['job_id'])
        self.assertEqual((item.user, item.service), (self.master.user, 'Skin fade'))

    def test_when_placid_fails_the_backup_generator_still_makes_an_image(self):
        with mock.patch('cloudinary.uploader.upload', return_value={'secure_url': 'https://cdn.test/x.png'}), \
                mock.patch.object(placid, 'create_image', side_effect=ConnectionError('placid down')):
            data = self.generate().json()
        self.assertEqual((data['status'], data['fallback']), ('finished', True))


class StatusTests(TestCase):
    def setUp(self):
        self.master = make_master('ana')
        self.client.force_login(self.master.user)
        self.item = PortfolioItem.objects.create(user=self.master.user, service='Fade', image='x.jpg')

    def test_finished_item_reports_its_image(self):
        self.item.generated_image = 'https://cdn.test/done.png'
        self.item.save()
        data = self.client.get(f'/instagram/status/{self.item.pk}/').json()
        self.assertEqual((data['status'], data['image_url']), ('finished', 'https://cdn.test/done.png'))

    def test_job_this_browser_never_started_is_404(self):
        self.assertEqual(self.client.get(f'/instagram/status/{self.item.pk}/').status_code, 404)

    def test_unknown_template_thumbnail_is_404(self):
        self.assertEqual(self.client.get('/instagram/thumbnail/not-a-template/').status_code, 404)


class PillowGeneratorTests(TempMediaTestCase):
    """The built-in generator (portfolio/utils.py) works offline for every style and size."""

    def setUp(self):
        self.photo = f'{self.media}/in.jpg'
        with open(self.photo, 'wb') as f:
            f.write(jpeg_bytes())

    def test_every_style_and_format_produces_an_image_of_the_right_size(self):
        for style in TEMPLATES:
            for fmt, size in FORMATS.items():
                with self.subTest(style=style, fmt=fmt):
                    out = f'{self.media}/{style}-{fmt}.png'
                    generate_instagram_image(self.photo, out, style, 'Skin fade', '@ana.cuts', fmt=fmt)
                    self.assertEqual(Image.open(out).size, (size['w'], size['h']))

    def test_unknown_style_or_format_falls_back_instead_of_crashing(self):
        out = f'{self.media}/fallback.png'
        generate_instagram_image(self.photo, out, 'no-such-style', '', '', fmt='billboard')
        self.assertEqual(Image.open(out).size, (FORMATS['story']['w'], FORMATS['story']['h']))

    def test_very_long_service_name_still_fits(self):
        out = f'{self.media}/long.png'
        generate_instagram_image(self.photo, out, 'stacked', 'Skin fade with beard sculpt ' * 10, 'ana')
        self.assertTrue(Image.open(out).size)
