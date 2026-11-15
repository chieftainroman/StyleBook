"""Tests for the public profile page and "Edit profile"."""
from decimal import Decimal

from django.test import TestCase

from accounts.models import Certificate, Honor, WorkExperience
from core.factories import make_master

EDIT_FORM = {
    'specialty': 'barber', 'bio': 'Five years of fades and tapers.', 'skills': 'Fades, tapers',
    'ig_handle': '@ana.cuts', 'location': 'Brooklyn', 'phone': '+1 555 0100', 'studio_name': 'Corner Cuts',
    'years_exp': '5', 'years_at_location': '2', 'travel_radius_km': '10', 'pricing_from': '25.50',
    'home_visits': 'on', 'languages': 'English, Russian, , Azerbaijani',
    'mon_open': '10:00', 'mon_close': '19:00', 'sun_closed': 'on',
    'min_lead_time_hours': '3', 'concurrent_clients': '2',
}


class PublicProfileTests(TestCase):
    def setUp(self):
        self.master = make_master('ana')

    def test_anyone_can_see_a_profile(self):
        response = self.client.get('/profile/ana/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'profile.html')
        self.assertFalse(response.context['is_own_profile'])

    def test_unknown_master_is_404(self):
        self.assertEqual(self.client.get('/profile/nobody/').status_code, 404)

    def test_owner_sees_it_as_their_own(self):
        self.client.force_login(self.master.user)
        self.assertTrue(self.client.get('/profile/ana/').context['is_own_profile'])

    def test_another_master_does_not_see_it_as_their_own(self):
        self.client.force_login(make_master('ben').user)
        self.assertFalse(self.client.get('/profile/ana/').context['is_own_profile'])

    def test_profile_shows_experience_certificates_and_honors(self):
        WorkExperience.objects.create(profile=self.master, title='Senior Barber', start_month=1,
                                      start_year=2020, is_current=True)
        Certificate.objects.create(profile=self.master, name='Master Barber', institution='NY Academy', year=2021)
        Honor.objects.create(profile=self.master, title='Best Fade 2024', year=2024)
        context = self.client.get('/profile/ana/').context
        self.assertEqual([e.title for e in context['experiences']], ['Senior Barber'])
        self.assertEqual([c.name for c in context['certificates']], ['Master Barber'])
        self.assertEqual([h.title for h in context['honors']], ['Best Fade 2024'])

    def test_my_profile_redirects_to_your_public_page(self):
        self.client.force_login(self.master.user)
        self.assertRedirects(self.client.get('/profile/'), '/profile/ana/', fetch_redirect_response=False)

    def test_my_profile_needs_login(self):
        self.assertTrue(self.client.get('/profile/')['Location'].startswith('/auth/login/'))


class EditProfilePageTests(TestCase):
    def setUp(self):
        self.master = make_master('ana')
        self.client.force_login(self.master.user)

    def test_every_tab_renders(self):
        for tab in ('basic', 'services', 'experience', 'certificates', 'honors', 'nonsense'):
            with self.subTest(tab=tab):
                self.assertEqual(self.client.get(f'/profile/edit/?tab={tab}').status_code, 200)

    def test_needs_login(self):
        self.client.logout()
        self.assertTrue(self.client.get('/profile/edit/')['Location'].startswith('/auth/login/'))


class EditProfileSaveTests(TestCase):
    def setUp(self):
        self.master = make_master('ana')
        self.client.force_login(self.master.user)

    def save(self, **overrides):
        response = self.client.post('/profile/edit/', {**EDIT_FORM, **overrides})
        self.master.refresh_from_db()
        return response

    def test_saving_goes_back_to_the_public_profile(self):
        self.assertRedirects(self.save(), '/profile/ana/', fetch_redirect_response=False)

    def test_text_fields_are_saved_trimmed(self):
        self.save(bio='  New bio here.  ', studio_name='  Corner Cuts ')
        self.assertEqual(self.master.bio, 'New bio here.')
        self.assertEqual(self.master.studio_name, 'Corner Cuts')

    def test_instagram_handle_loses_its_at_sign(self):
        self.save()
        self.assertEqual(self.master.ig_handle, 'ana.cuts')

    def test_languages_are_split_on_commas_and_blanks_dropped(self):
        self.save()
        self.assertEqual(self.master.languages, ['English', 'Russian', 'Azerbaijani'])

    def test_checkbox_off_means_false(self):
        self.save()
        self.assertTrue(self.master.home_visits)
        form = dict(EDIT_FORM)
        del form['home_visits']
        self.client.post('/profile/edit/', form)
        self.master.refresh_from_db()
        self.assertFalse(self.master.home_visits)

    def test_numbers_are_parsed_and_bad_numbers_do_not_crash(self):
        self.save()
        self.assertEqual((self.master.years_exp, self.master.travel_radius_km, self.master.pricing_from),
                         (5, 10, Decimal('25.50')))
        self.save(years_exp='lots', travel_radius_km='', pricing_from='cheap')
        self.assertEqual((self.master.years_exp, self.master.travel_radius_km, self.master.pricing_from),
                         (0, None, None))

    def test_lead_time_is_kept_between_0_and_168_hours(self):
        for sent, stored in (('-5', 0), ('3', 3), ('500', 168), ('soon', 2)):
            with self.subTest(sent=sent):
                self.save(min_lead_time_hours=sent)
                self.assertEqual(self.master.min_lead_time_hours, stored)

    def test_capacity_is_kept_between_1_and_20(self):
        for sent, stored in (('0', 1), ('2', 2), ('99', 20), ('many', 1)):
            with self.subTest(sent=sent):
                self.save(concurrent_clients=sent)
                self.assertEqual(self.master.concurrent_clients, stored)

    def test_working_hours_grid_is_saved(self):
        self.save()
        self.assertEqual(self.master.working_hours['mon'], {'open': '10:00', 'close': '19:00', 'closed': False})
        self.assertTrue(self.master.working_hours['sun']['closed'])
