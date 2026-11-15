"""
The most important security rule on the profile side: a master can never
change or delete another master's things by guessing a number in the URL.

Every test logs in as Ana and attacks something that belongs to Ben.
The right answer is always a 404 ("not found") and Ben's data untouched.
"""
import json

from django.test import TestCase

from accounts.models import Certificate, Honor, Service, WorkExperience
from core.factories import make_master, make_service
from portfolio.models import PortfolioItem


class OwnershipTests(TestCase):
    def setUp(self):
        self.ana = make_master('ana')
        self.ben = make_master('ben')
        self.bens_service = make_service(self.ben, 'Ben cut', sort_order=5)
        self.bens_job = WorkExperience.objects.create(profile=self.ben, title='Ben job', start_month=1,
                                                      start_year=2020, is_current=True)
        self.bens_cert = Certificate.objects.create(profile=self.ben, name='Ben cert', institution='X', year=2020)
        self.bens_honor = Honor.objects.create(profile=self.ben, title='Ben honor', year=2020)
        self.client.force_login(self.ana.user)

    def assert_404(self, url, data=None):
        response = self.client.post(url, data or {})
        self.assertEqual(response.status_code, 404, url)

    def test_cannot_edit_hide_or_delete_someone_elses_service(self):
        pk = self.bens_service.pk
        self.assert_404(f'/profile/service/{pk}/edit/', {'name': 'Hacked', 'duration_minutes': '30', 'price': '1'})
        self.assert_404(f'/profile/service/{pk}/toggle/')
        self.assert_404(f'/profile/service/{pk}/delete/')
        self.bens_service.refresh_from_db()
        self.assertEqual((self.bens_service.name, self.bens_service.is_active), ('Ben cut', True))

    def test_cannot_reorder_someone_elses_services(self):
        self.client.post('/profile/service/reorder/', data=json.dumps({'ids': [self.bens_service.pk]}),
                         content_type='application/json')
        self.bens_service.refresh_from_db()
        self.assertEqual(self.bens_service.sort_order, 5)

    def test_cannot_edit_or_delete_someone_elses_experience(self):
        job = {'title': 'Hacked', 'start_month': '1', 'start_year': '2020', 'is_current': 'on'}
        self.assert_404(f'/profile/experience/{self.bens_job.pk}/edit/', job)
        self.assert_404(f'/profile/experience/{self.bens_job.pk}/delete/')
        self.bens_job.refresh_from_db()
        self.assertEqual(self.bens_job.title, 'Ben job')

    def test_cannot_edit_or_delete_someone_elses_certificate(self):
        cert = {'name': 'Hacked', 'institution': 'X', 'year': '2020'}
        self.assert_404(f'/profile/certificate/{self.bens_cert.pk}/edit/', cert)
        self.assert_404(f'/profile/certificate/{self.bens_cert.pk}/delete/')
        self.assertTrue(Certificate.objects.filter(pk=self.bens_cert.pk, name='Ben cert').exists())

    def test_cannot_edit_or_delete_someone_elses_honor(self):
        self.assert_404(f'/profile/honor/{self.bens_honor.pk}/edit/', {'title': 'Hacked', 'year': '2020'})
        self.assert_404(f'/profile/honor/{self.bens_honor.pk}/delete/')
        self.assertTrue(Honor.objects.filter(pk=self.bens_honor.pk, title='Ben honor').exists())

    def test_cannot_poll_someone_elses_instagram_job(self):
        item = PortfolioItem.objects.create(user=self.ben.user, service='Fade', image='x.jpg')
        self.assertEqual(self.client.get(f'/instagram/status/{item.pk}/').status_code, 404)

    def test_new_things_are_always_created_on_your_own_profile(self):
        self.client.post('/profile/service/add/', {'name': 'Mine', 'duration_minutes': '30', 'price': '10',
                                                   'profile': self.ben.pk})       # trying to sneak in Ben's id
        self.assertEqual(Service.objects.get(name='Mine').profile, self.ana)

    def test_your_own_things_still_work(self):
        mine = make_service(self.ana, 'Mine')
        self.assertEqual(self.client.post(f'/profile/service/{mine.pk}/toggle/').status_code, 200)
