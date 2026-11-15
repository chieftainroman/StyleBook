"""
Tests for the 5-step onboarding wizard (/onboarding/).

Steps 1, 3 and 5 are required and save data; steps 2 and 4 are optional.
"""
from django.contrib.auth.models import User
from django.test import TestCase

from core.factories import make_master

FULL_STEP_5 = {
    'phone': '+1 555 0100', 'ig_handle': '@ana.cuts',
    'mon_open': '10:00', 'mon_close': '19:00',
    'sun_closed': 'on',
}


class WizardTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ana', 'ana@example.com', 'secret-123')
        self.profile = self.user.profile
        self.client.force_login(self.user)

    def save(self, step, data):
        return self.client.post(f'/onboarding/step/{step}/save/', data)

    def refresh(self):
        self.profile.refresh_from_db()
        return self.profile


class WizardPageTests(WizardTestCase):
    def test_wizard_opens_on_step_1(self):
        response = self.client.get('/onboarding/')
        self.assertTemplateUsed(response, 'onboarding/wizard.html')
        self.assertEqual(response.context['step'], 1)

    def test_every_step_renders(self):
        for step in range(1, 6):
            with self.subTest(step=step):
                response = self.client.get(f'/onboarding/?step={step}')
                self.assertEqual(response.context['step'], step)
                self.assertEqual(response.context['is_last'], step == 5)

    def test_bad_step_numbers_fall_back_to_step_1(self):
        for bad in ('0', '6', '-1', 'abc', ''):
            with self.subTest(step=bad):
                self.assertEqual(self.client.get(f'/onboarding/?step={bad}').context['step'], 1)

    def test_finished_master_is_sent_to_dashboard(self):
        self.profile.onboarding_completed = True
        self.profile.save()
        self.assertRedirects(self.client.get('/onboarding/'), '/dashboard/', fetch_redirect_response=False)
        self.assertRedirects(self.save(1, {}), '/dashboard/', fetch_redirect_response=False)

    def test_anonymous_visitor_must_log_in(self):
        self.client.logout()
        self.assertTrue(self.client.get('/onboarding/')['Location'].startswith('/auth/login/'))

    def test_save_only_accepts_post(self):
        self.assertEqual(self.client.get('/onboarding/step/1/save/').status_code, 405)


class StepOneTests(WizardTestCase):
    def test_missing_or_bad_fields_are_refused(self):
        cases = {
            'no specialty': {'specialty': '', 'location': 'Brooklyn', 'years_exp': '3'},
            'no location': {'specialty': 'barber', 'location': ' ', 'years_exp': '3'},
            'zero years': {'specialty': 'barber', 'location': 'Brooklyn', 'years_exp': '0'},
            'years not a number': {'specialty': 'barber', 'location': 'Brooklyn', 'years_exp': 'ten'},
        }
        for label, data in cases.items():
            with self.subTest(label):
                response = self.save(1, data)
                self.assertRedirects(response, '/onboarding/?step=1', fetch_redirect_response=False)
                self.assertEqual(self.refresh().specialty, '')

    def test_valid_step_saves_and_moves_to_step_2(self):
        response = self.save(1, {'specialty': 'barber', 'location': 'Brooklyn', 'years_exp': '3'})
        self.assertRedirects(response, '/onboarding/?step=2', fetch_redirect_response=False)
        profile = self.refresh()
        self.assertEqual((profile.specialty, profile.location, profile.years_exp), ('barber', 'Brooklyn', 3))


class OptionalStepTests(WizardTestCase):
    def test_steps_2_and_4_just_move_on(self):
        self.assertRedirects(self.save(2, {}), '/onboarding/?step=3', fetch_redirect_response=False)
        self.assertRedirects(self.save(4, {}), '/onboarding/?step=5', fetch_redirect_response=False)


class StepThreeTests(WizardTestCase):
    def test_bio_shorter_than_20_characters_is_refused(self):
        self.save(3, {'bio': 'Too short'})
        self.assertEqual(self.refresh().bio, '')

    def test_bio_is_saved_trimmed(self):
        self.save(3, {'bio': '   Five years of fades, tapers and beard work.  '})
        self.assertEqual(self.refresh().bio, 'Five years of fades, tapers and beard work.')


class StepFiveTests(WizardTestCase):
    def test_phone_is_required(self):
        response = self.save(5, {**FULL_STEP_5, 'phone': ''})
        self.assertRedirects(response, '/onboarding/?step=5', fetch_redirect_response=False)
        self.assertEqual(self.refresh().phone, '')

    def test_contact_and_hours_are_saved_then_onboarding_finishes(self):
        response = self.save(5, FULL_STEP_5)
        self.assertRedirects(response, '/onboarding/finish/', fetch_redirect_response=False)
        profile = self.refresh()
        self.assertEqual(profile.phone, '+1 555 0100')
        self.assertEqual(profile.ig_handle, 'ana.cuts')                          # "@" removed
        self.assertEqual(profile.working_hours['mon'], {'open': '10:00', 'close': '19:00', 'closed': False})
        self.assertTrue(profile.working_hours['sun']['closed'])
        self.assertEqual(profile.working_hours['tue']['open'], '09:00')          # default when not sent


class FinishTests(WizardTestCase):
    def test_finish_marks_onboarding_done(self):
        self.assertRedirects(self.client.get('/onboarding/finish/'), '/dashboard/', fetch_redirect_response=False)
        self.assertTrue(self.refresh().onboarding_completed)

    def test_skip_does_the_same(self):
        self.client.get('/onboarding/skip/')
        self.assertTrue(self.refresh().onboarding_completed)


class NewMasterJourneyTests(TestCase):
    """The whole path a new master takes on Monday, start to finish."""

    def test_register_onboard_add_a_service_and_take_bookings(self):
        self.client.post('/auth/register/', {'username': 'ana', 'email': 'ana@example.com', 'password': 'secret-123'})
        self.assertRedirects(self.client.get('/dashboard/'), '/onboarding/', fetch_redirect_response=False)

        self.client.post('/onboarding/step/1/save/', {'specialty': 'barber', 'location': 'Brooklyn', 'years_exp': '3'})
        self.client.post('/onboarding/step/3/save/', {'bio': 'Five years of fades, tapers and beard work.'})
        self.client.post('/onboarding/step/5/save/', FULL_STEP_5)
        self.client.get('/onboarding/finish/')
        self.assertEqual(self.client.get('/dashboard/').status_code, 200)

        self.assertTemplateUsed(self.client.get('/book/ana/'), 'bookings/not_available.html')   # no services yet
        self.client.post('/profile/service/add/', {'name': 'Haircut', 'duration_minutes': '30', 'price': '40'})
        self.assertTemplateUsed(self.client.get('/book/ana/'), 'bookings/book.html')


class ProfileFactoryCheck(TestCase):
    def test_factory_master_is_fully_onboarded(self):
        """Guard for core/factories.py itself: other tests rely on this."""
        master = make_master('check')
        self.assertTrue(master.is_complete())
        self.assertTrue(master.onboarding_completed)
