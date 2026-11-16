"""
Bugs that cut across the whole app.
Tests tagged `known_bug` fail until their fix is applied (see accounts/tests/test_bugs.py).
"""
import inspect
import pathlib

from django.conf import settings
from django.core import mail
from django.test import TestCase, tag

from core.factories import make_master
from portfolio import utils

TEMPLATES_DIR = pathlib.Path(settings.BASE_DIR) / 'templates'


class BrandingBugs(TestCase):
    # ── Bug 16 ───────────────────────────────────────────────────────────
    def test_bug16_no_page_shows_the_old_name(self):
        """
        Page titles, the 404/500 pages, Google sign-up and password pages
        still say "StyleBook". Clients who don't know that name think it's
        spam or a different site. Correct: "Showpiece" everywhere users look.
        """
        offenders = sorted(str(p.relative_to(TEMPLATES_DIR)) for p in TEMPLATES_DIR.rglob('*.*')
                           if 'StyleBook' in p.read_text(encoding='utf-8', errors='ignore'))
        self.assertEqual(offenders, [], 'templates that still say StyleBook')

    def test_bug16b_no_email_or_message_shows_the_old_name(self):
        make_master('ana', email='ana@example.com')
        self.client.post('/auth/forgot-password/', {'email': 'ana@example.com'})
        self.client.force_login(make_master('ben', email='ben@example.com').user)
        self.client.get('/auth/resend-verification/')
        for email in mail.outbox:
            with self.subTest(subject=email.subject):
                self.assertNotIn('StyleBook', email.subject + email.body)
        self.client.logout()
        welcome = self.client.post('/auth/register/', {'username': 'cy', 'email': 'cy@example.com',
                                                       'password': 'secret-123', 'specialty': 'barber'}, follow=True)
        self.assertNotContains(welcome, 'Welcome to StyleBook')

    def test_bug16c_downloads_and_generated_images_use_the_new_name(self):
        master = make_master('dee')
        self.client.force_login(master.user)
        disposition = self.client.get('/qr/dee.png?download=1')['Content-Disposition']
        self.assertNotIn('stylebook', disposition.lower())
        self.assertNotIn('"StyleBook"', inspect.getsource(utils), 'Instagram images are watermarked StyleBook')
