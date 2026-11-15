"""Tests for work experience, certificates and honors on a master's profile."""
from django.test import TestCase

from accounts.models import Certificate, Honor, WorkExperience
from core.factories import make_master

JOB = {'title': 'Senior Barber', 'studio_name': 'Corner Cuts', 'city': 'Brooklyn',
       'start_month': '3', 'start_year': '2020', 'end_month': '6', 'end_year': '2023', 'description': 'Fades'}
CERT = {'name': 'Master Barber', 'institution': 'NY Barber Academy', 'year': '2021',
        'file_url': 'https://res.cloudinary.com/demo/raw/upload/cert.pdf', 'file_kind': 'pdf'}
HONOR = {'title': 'Best Fade', 'issuer': 'Brooklyn Barber Expo', 'year': '2024', 'description': 'First place'}


class AchievementTestCase(TestCase):
    def setUp(self):
        self.master = make_master('ana')
        self.client.force_login(self.master.user)


class ExperienceTests(AchievementTestCase):
    def add(self, **overrides):
        return self.client.post('/profile/experience/add/', {**JOB, **overrides})

    def test_add_saves_the_job(self):
        response = self.add()
        self.assertRedirects(response, '/profile/edit/?tab=experience', fetch_redirect_response=False)
        job = WorkExperience.objects.get(profile=self.master)
        self.assertEqual((job.title, job.start_year, job.end_year, job.is_current), ('Senior Barber', 2020, 2023, False))

    def test_current_job_ignores_any_end_date(self):
        self.add(is_current='on', end_month='', end_year='')
        job = WorkExperience.objects.get()
        self.assertTrue(job.is_current)
        self.assertIsNone(job.end_year)

    def test_invalid_jobs_are_refused(self):
        cases = {
            'no title': {'title': ''},
            'start month 0': {'start_month': '0'},
            'start month 13': {'start_month': '13'},
            'start year 1949': {'start_year': '1949'},
            'start year 2101': {'start_year': '2101'},
            'start not a number': {'start_year': 'last year'},
            'finished job without an end date': {'end_month': '', 'end_year': ''},
            'end month 13': {'end_month': '13'},
        }
        for label, overrides in cases.items():
            with self.subTest(label):
                self.add(**overrides)
        self.assertFalse(WorkExperience.objects.exists())

    def test_edit_and_delete(self):
        self.add()
        job = WorkExperience.objects.get()
        self.client.post(f'/profile/experience/{job.pk}/edit/', {**JOB, 'title': 'Head Barber'})
        job.refresh_from_db()
        self.assertEqual(job.title, 'Head Barber')
        self.client.post(f'/profile/experience/{job.pk}/edit/', {**JOB, 'title': ''})      # invalid: no change
        job.refresh_from_db()
        self.assertEqual(job.title, 'Head Barber')
        self.client.post(f'/profile/experience/{job.pk}/delete/')
        self.assertFalse(WorkExperience.objects.exists())


class CertificateTests(AchievementTestCase):
    def add(self, **overrides):
        return self.client.post('/profile/certificate/add/', {**CERT, **overrides})

    def test_add_saves_the_certificate(self):
        self.assertRedirects(self.add(), '/profile/edit/?tab=certificates', fetch_redirect_response=False)
        cert = Certificate.objects.get(profile=self.master)
        self.assertEqual((cert.name, cert.institution, cert.year, cert.file_kind),
                         ('Master Barber', 'NY Barber Academy', 2021, 'pdf'))

    def test_invalid_certificates_are_refused(self):
        for label, overrides in {'no name': {'name': ''}, 'no institution': {'institution': ''},
                                 'year 1949': {'year': '1949'}, 'year 2101': {'year': '2101'},
                                 'year not a number': {'year': 'soon'}}.items():
            with self.subTest(label):
                self.add(**overrides)
        self.assertFalse(Certificate.objects.exists())

    def test_edit_and_delete(self):
        self.add()
        cert = Certificate.objects.get()
        self.client.post(f'/profile/certificate/{cert.pk}/edit/', {**CERT, 'year': '2022'})
        cert.refresh_from_db()
        self.assertEqual(cert.year, 2022)
        self.client.post(f'/profile/certificate/{cert.pk}/delete/')
        self.assertFalse(Certificate.objects.exists())


class HonorTests(AchievementTestCase):
    def add(self, **overrides):
        return self.client.post('/profile/honor/add/', {**HONOR, **overrides})

    def test_add_saves_the_honor(self):
        self.assertRedirects(self.add(), '/profile/edit/?tab=honors', fetch_redirect_response=False)
        honor = Honor.objects.get(profile=self.master)
        self.assertEqual((honor.title, honor.issuer, honor.year), ('Best Fade', 'Brooklyn Barber Expo', 2024))

    def test_issuer_is_optional(self):
        self.add(issuer='')
        self.assertTrue(Honor.objects.exists())

    def test_invalid_honors_are_refused(self):
        for label, overrides in {'no title': {'title': ''}, 'year 1949': {'year': '1949'},
                                 'year not a number': {'year': 'x'}}.items():
            with self.subTest(label):
                self.add(**overrides)
        self.assertFalse(Honor.objects.exists())

    def test_edit_and_delete(self):
        self.add()
        honor = Honor.objects.get()
        self.client.post(f'/profile/honor/{honor.pk}/edit/', {**HONOR, 'title': 'Best Taper'})
        honor.refresh_from_db()
        self.assertEqual(honor.title, 'Best Taper')
        self.client.post(f'/profile/honor/{honor.pk}/delete/')
        self.assertFalse(Honor.objects.exists())

    def test_all_achievement_actions_need_post(self):
        for url in ('/profile/experience/add/', '/profile/certificate/add/', '/profile/honor/add/'):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 405)
